/** Prevent dismissing a dialog while its non-cancellable operation is pending. */
export function dismissUnlessBusy(busy: boolean, onClose: () => void): boolean {
  if (busy) return false;
  onClose();
  return true;
}
