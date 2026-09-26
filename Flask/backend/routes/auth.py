"""auth 模块路由（蓝本）"""
from flask import request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

from flask import Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt, create_access_token

from backend.extensions import db, redis_client
from backend.config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
from backend.models import User
from backend.utils import (
    generate_code, send_email, encrypt_password, verify_password, fix_image_url,
    is_legacy_password_hash
)

bp = Blueprint('auth', __name__)

@bp.route('/api/register', methods=['POST'])
def register():
    """校验验证码，创建用户和用户详情"""
    try:
        data = request.get_json(silent=True) or {}
        # trim 与登录侧一致，防止首尾空格导致"注册后登录不上"
        nickname = (data.get('nickname') or '').strip()
        username = (data.get('username') or '').strip()
        password = (data.get('password') or '').strip()
        role = (data.get('role') or '').strip()
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()

        if not all([nickname, username, password, role, email, code]):
            return jsonify({'code': 400, 'msg': '请完善所有信息'})

        if role not in ('user', 'merchant'):
            return jsonify({'code': 400, 'msg': '角色不合法'}), 400

        if len(password) < 6:
            return jsonify({'code': 400, 'msg': '密码长度不能少于6位'}), 400

        # 校验验证码（限制尝试次数，防 6 位码暴力枚举）
        try_count = redis_client.incr(f"code_try:{email}")
        if try_count == 1:
            redis_client.expire(f"code_try:{email}", 600)  # 计数 10 分钟自愈，避免用户被永久锁定
        if try_count > 10:
            return jsonify({'code': 429, 'msg': '验证码尝试次数过多，请重新获取'}), 429
        stored_code = redis_client.get(f"code:{email}")
        if not stored_code or stored_code != code:
            return jsonify({'code': 400, 'msg': '验证码错误或已过期'})

        if User.query.filter_by(username=username).first():
            return jsonify({'code': 400, 'msg': '用户名已存在'})

        new_user = User(
            nickname=nickname,
            username=username,
            password=encrypt_password(password),
            role=role,
            email=email
        )
        db.session.add(new_user)
        db.session.commit()

        try:
            today_key = datetime.now().strftime('%Y%m%d')
            redis_client.incr(f'monitor:new_registrations:{today_key}')
            redis_client.expire(f'monitor:new_registrations:{today_key}', 86400 * 7)
        except Exception:
            pass

        redis_client.delete(f"code:{email}")  # 注册成功后清除验证码
        redis_client.delete(f"code_try:{email}")  # 成功即清零尝试计数
        access_token = create_access_token(
            identity=str(new_user.id),
            additional_claims={'id': new_user.id, 'role': role, 'nickname': new_user.nickname})
        return jsonify({
            'code': 200,
            'msg': '注册成功',
            'token': access_token,
            'nickname': new_user.nickname,
            'role': role,
            'userId': new_user.id
        })
    except Exception as e:
        db.session.rollback()
        print(f"注册失败：{e}")
        return jsonify({'code': 500, 'msg': '服务器异常，注册失败'})

@bp.route('/api/login', methods=['POST'])
def login():
    """用户登录，返回JWT token"""
    try:
        data = request.get_json(silent=True) or {}
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        user = User.query.filter_by(username=username, role=role).first()
        if not user:
            return jsonify({'code': 400, 'msg': '用户名/密码/角色错误'})
        # 密码校验：兼容「werkzeug 哈希（新）」与「Fernet 密文（历史数据）」
        if not verify_password(user.password, password):
            return jsonify({'code': 400, 'msg': '用户名/密码/角色错误'})

        if is_legacy_password_hash(user.password):
            try:
                user.password = encrypt_password(password)
                db.session.commit()
            except Exception:
                db.session.rollback()

        if user.is_banned:
            return jsonify({'code': 403, 'msg': '您的账号已被封禁，请联系管理员'}), 403

        access_token = create_access_token(identity=str(user.id),additional_claims={'id': user.id, 'role': role, 'nickname': user.nickname})
        return jsonify({
            'code': 200,
            'msg': '登录成功',
            'token': access_token,
            'nickname': user.nickname,
            'role': role,
            'userId': user.id
        })
    except Exception as e:
        print(f"登录错误: {e}")
        return jsonify({'code': 500, 'msg': '登录失败，请稍后重试'}), 500

@bp.route('/api/logout', methods=['POST'])
@jwt_required()
def logout():
    """登出：将当前token加入黑名单"""
    jti = get_jwt()['jti']
    redis_client.setex(f"jwt_blacklist:{jti}", current_app.config['JWT_ACCESS_TOKEN_EXPIRES'], 1)
    return jsonify({'code': 200, 'msg': '登出成功'})

@bp.route('/api/send_code', methods=['POST'])
def send_code():
    """发送邮箱验证码（用于注册）"""
    import re
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    # 严格校验：必须形如  xxx@qq.com（防止 x@qq.com.evil.com 之类绕过）
    if not re.fullmatch(r'[^@\s]+@qq\.com', email):
        return jsonify({'code': 400, 'msg': '请输入有效的QQ邮箱'}), 400

    # 频率限制：同一邮箱 60s 一次、同一 IP 60s 5 次，防止邮件轰炸/刷接口
    ip = request.remote_addr or '0.0.0.0'
    if not redis_client.set(f"code_limit:email:{email}", 1, nx=True, ex=60):
        return jsonify({'code': 429, 'msg': '验证码发送过于频繁，请稍后再试'}), 429
    ip_key = f"code_limit:ip:{ip}"
    ip_hits = redis_client.incr(ip_key)
    if ip_hits == 1:
        redis_client.expire(ip_key, 60)
    if ip_hits > 5:
        return jsonify({'code': 429, 'msg': '操作过于频繁，请稍后再试'}), 429

    code = generate_code()
    redis_client.setex(f"code:{email}", 300, code)  # 验证码5分钟有效
    redis_client.setex(f"code_try:{email}", 300, 0)  # 校验次数计数（防暴力破解）
    if send_email(email, code):
        return jsonify({'code': 200, 'msg': '验证码已发送到QQ邮箱'})
    else:
        return jsonify({'code': 500, 'msg': '验证码发送失败，请检查邮箱'})

@bp.route('/api/reset-password-send', methods=['POST'])
def reset_password_send_code():
    """发送找回密码验证码"""
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()

        if not username:
            return jsonify({'code': 400, 'msg': '请输入账号'}), 400
        if not email or '@' not in email:
            return jsonify({'code': 400, 'msg': '请输入有效的邮箱'}), 400

        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'code': 400, 'msg': '账号不存在'}), 400

        if (user.email or '') != email:
            return jsonify({'code': 400, 'msg': '账号与邮箱不匹配'}), 400

        code = generate_code()
        redis_client.setex(f"reset_code:{username}:{email}", 300, code)

        msg = MIMEText(f'您的找回密码验证码是：{code}，5分钟内有效，请勿泄露。', 'plain', 'utf-8')
        msg['From'] = f"{Header('次元模仓', 'utf-8').encode()} <{SMTP_USER}>"
        msg['To'] = email
        msg['Subject'] = Header('【次元模仓】找回密码验证码', 'utf-8')

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [email], msg.as_string())

        return jsonify({'code': 200, 'msg': '验证码已发送到邮箱'})
    except Exception as e:
        print(f"发送找回密码验证码失败: {e}")
        return jsonify({'code': 500, 'msg': '验证码发送失败'}), 500

@bp.route('/api/reset-password-reset', methods=['POST'])
def reset_password():
    """重置密码"""
    try:
        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()
        code = (data.get('code') or '').strip()
        new_password = (data.get('newPassword') or '').strip()

        if not all([username, email, code, new_password]):
            return jsonify({'code': 400, 'msg': '请完善所有信息'}), 400

        if len(new_password) < 6:
            return jsonify({'code': 400, 'msg': '密码长度不能少于6位'}), 400

        stored_code = redis_client.get(f"reset_code:{username}:{email}")
        if not stored_code or stored_code != code:
            return jsonify({'code': 400, 'msg': '验证码错误或已过期'}), 400

        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({'code': 400, 'msg': '账号不存在'}), 400

        if (user.email or '') != email:
            return jsonify({'code': 400, 'msg': '账号与邮箱不匹配'}), 400

        if verify_password(user.password, new_password):
            return jsonify({'code': 400, 'msg': '新密码不能与当前密码相同'}), 400

        user.password = encrypt_password(new_password)
        redis_client.delete(f"reset_code:{username}:{email}")
        db.session.commit()

        return jsonify({'code': 200, 'msg': '密码重置成功，请登录'})
    except Exception as e:
        db.session.rollback()
        print(f"重置密码失败: {e}")
        return jsonify({'code': 500, 'msg': '重置密码失败'}), 500

@bp.route('/api/user/info', methods=['GET'])
@jwt_required()
def user_info():
    """获取当前登录用户的详细信息"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        if not user:
            return jsonify({'code': 404, 'msg': '用户不存在'})

        addr_text = user.address or ''
        address_struct = {
            'name': user.receiver_name or '',
            'phone': user.phone or '',
            'province': '', 'city': '', 'district': '', 'detail': addr_text
        }
        address_parts = addr_text.split('省')
        if len(address_parts) > 1:
            address_struct['province'] = address_parts[0] + '省'
            remaining = address_parts[1]
            city_parts = remaining.split('市')
            if len(city_parts) > 1:
                address_struct['city'] = city_parts[0] + '市'
                remaining = city_parts[1]
                district_parts = remaining.split('区')
                if len(district_parts) > 1:
                    address_struct['district'] = district_parts[0] + '区'
                    address_struct['detail'] = district_parts[1]
                else:
                    address_struct['detail'] = remaining
            else:
                address_struct['detail'] = remaining

        return jsonify({
            'code': 200,
            'data': {
                'nickname': user.nickname,
                'avatar': fix_image_url(user.avatar or ''),
                'birthday': user.birthday or '',
                'gender': user.gender or 'secret',
                'phone': user.phone or '',
                'receiverName': user.receiver_name or '',
                'address': addr_text,
                'address_struct': address_struct
            }
        })
    except Exception as e:
        print(f"获取用户信息错误: {e}")
        return jsonify({'code': 500, 'msg': '服务器错误'})

@bp.route('/api/user/update', methods=['POST'])
@jwt_required()
def update_info():
    """生日、性别、收货人、电话、地址"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        user = User.query.get(user_id)
        if not user:
            return jsonify({'code': 404, 'msg': '用户不存在'})
        user.birthday = data.get('birthday', '')
        user.gender = data.get('gender', 'secret')
        user.receiver_name = data.get('receiverName', data.get('name', ''))
        user.phone = data.get('phone', '')
        if 'address_struct' in data:
            addr = data['address_struct']
            user.address = f"{addr.get('province', '')}{addr.get('city', '')}{addr.get('district', '')}{addr.get('detail', '')}"
        elif 'address' in data and data['address']:
            user.address = data['address']
        db.session.commit()
        return jsonify({'code': 200, 'msg': '保存成功'})
    except Exception as e:
        print(f"更新信息错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '保存失败'})

@bp.route('/api/user/update-nickname', methods=['POST'])
@jwt_required()
def update_nickname():
    """修改用户昵称"""
    try:
        user_id = int(get_jwt_identity())
        nickname = (request.get_json(silent=True) or {}).get('nickname')
        if not nickname:
            return jsonify({'code': 400, 'msg': '昵称不能为空'})
        if len(nickname) > 80:
            return jsonify({'code': 400, 'msg': '昵称长度不能超过80个字符'})
        user = User.query.get(user_id)
        user.nickname = nickname
        db.session.commit()
        return jsonify({'code': 200, 'msg': '修改成功'})
    except Exception as e:
        print(f"修改昵称错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '修改失败'})

@bp.route('/api/user/update-avatar', methods=['POST'])
@jwt_required()
def update_avatar():
    """更新用户头像URL"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        avatar = (data.get('avatar') or '').strip()
        if not avatar:
            return jsonify({'code': 400, 'msg': '头像地址不能为空'})
        user = User.query.get(user_id)
        if not user:
            return jsonify({'code': 404, 'msg': '用户不存在'})
        user.avatar = fix_image_url(avatar)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '头像更新成功'})
    except Exception as e:
        print(f"更新头像错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '头像更新失败'})

@bp.route('/api/user/update-password', methods=['POST'])
@jwt_required()
def update_password():
    """需验证原密码"""
    try:
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        old_pwd = data.get('oldPassword')
        new_pwd = data.get('newPassword')
        user = User.query.get(user_id)
        if not verify_password(user.password, old_pwd):
            return jsonify({'code': 400, 'msg': '原密码错误'})
        if not new_pwd or len(new_pwd) < 6:
            return jsonify({'code': 400, 'msg': '新密码长度不能少于6位'})
        user.password = encrypt_password(new_pwd)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '修改成功，请重新登录'})
    except Exception as e:
        print(f"修改密码错误: {e}")
        db.session.rollback()
        return jsonify({'code': 500, 'msg': '修改失败'})

