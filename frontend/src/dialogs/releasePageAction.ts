import { t } from "../i18n/index.ts";
/** Keep the update dialog open when the system browser could not be launched. */
export async function runReleasePageAction(
  openPage: () => Promise<{ ok: boolean; url: string }>,
  onOpened: () => void,
  onError: (message: string) => void,
): Promise<void> {
  try {
    const result = await openPage();
    if (!result.ok) {
      onError(t("release.open_failed_url", { url: result.url }));
      return;
    }
    onOpened();
  } catch (error) {
    onError(t("release.open_failed", { error: String(error) }));
  }
}
