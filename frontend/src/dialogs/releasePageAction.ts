/** Keep the update dialog open when the system browser could not be launched. */
export async function runReleasePageAction(
  openPage: () => Promise<{ ok: boolean; url: string }>,
  onOpened: () => void,
  onError: (message: string) => void,
): Promise<void> {
  try {
    const result = await openPage();
    if (!result.ok) {
      onError(`リリースページを開けませんでした。URL: ${result.url}`);
      return;
    }
    onOpened();
  } catch (error) {
    onError(`リリースページを開けませんでした: ${String(error)}`);
  }
}
