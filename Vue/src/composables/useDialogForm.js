/**
 * useDialogForm —— 后台弹窗表单通用逻辑
 * ------------------------------------------------------------------
 * 原先每个 admin 弹窗（商品/订单/用户/详情）都各自重复写一遍：
 *   - visibleDialog 的 computed 读写（props.visible <-> emit('update:visible')）
 *   - formRef / saving 状态
 *   - resetForm() / handleClose()
 * 这里把它们抽成组合式函数，所有弹窗统一引入，减少重复、行为一致。
 *
 * 约定：调用方组件的 props 必须含 `visible: Boolean`，
 *       emits 必须含 `'update:visible'` 与（可选）`'saved'`。
 *
 * @param {Object} props  组件的 props（需含 visible）
 * @param {Function} emit 组件的 emit
 * @returns {{ visibleDialog: import('vue').ComputedRef<boolean>,
 *             formRef: import('vue').Ref, saving: import('vue').Ref<boolean>,
 *             handleClose: Function, resetForm: Function }}
 */
import { ref, computed } from 'vue'

export function useDialogForm(props, emit) {
  const visibleDialog = computed({
    get: () => props.visible,
    set: (v) => emit('update:visible', v)
  })

  const formRef = ref()
  const saving = ref(false)

  const handleClose = () => {
    visibleDialog.value = false
  }

  const resetForm = () => {
    formRef.value?.clearValidate()
    saving.value = false
  }

  return { visibleDialog, formRef, saving, handleClose, resetForm }
}
