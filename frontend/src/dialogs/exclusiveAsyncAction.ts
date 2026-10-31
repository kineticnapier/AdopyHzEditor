/** Allow only one in-flight operation; subsequent attempts may retry after settlement. */
export function createExclusiveAsyncAction() {
  let pending = false;
  return async function run<T>(action: () => Promise<T>): Promise<T | undefined> {
    if (pending) return undefined;
    pending = true;
    try {
      return await action();
    } finally {
      pending = false;
    }
  };
}
