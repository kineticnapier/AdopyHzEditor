/** Report failed clipboard/file actions without losing the current Quick Hz preview. */
export async function runQuickHzOutputAction<T>(
  label: string,
  action: () => Promise<T>,
  onSuccess: (result: T) => void,
  onError: (message: string) => void,
): Promise<void> {
  let result: T;
  try {
    result = await action();
  } catch (error) {
    onError(`${label}に失敗しました: ${String(error)}`);
    return;
  }
  onSuccess(result);
}
