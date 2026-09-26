import { ElMessageBox } from 'element-plus'

export function showAlert(msg, title = '提示', type = 'info') {
  const boxType = type === 'confirm' ? 'warning' : type
  return ElMessageBox.alert(msg, title, {
    type: boxType,
    confirmButtonText: '确定',
    closeOnClickModal: false,
  })
}

export function showConfirm(msg, title = '确认操作') {
  return ElMessageBox.confirm(msg, title, {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => true).catch(() => false)
}
