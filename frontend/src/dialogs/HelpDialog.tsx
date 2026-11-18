import { useEffect, useRef, useState } from "react";
import type { BackendApi, HelpPayload } from "./bridge";
import { useDialogAccessibility } from "./useDialogAccessibility";
import { createExclusiveAsyncAction } from "./exclusiveAsyncAction";
import { dismissUnlessBusy } from "./dialogClosePolicy";
import { runReleasePageAction } from "./releasePageAction";
import { blankWorkspaceDefaultsContextIsCurrent } from "./previewFreshness";
type Props = { api: BackendApi; initialSection?: string; onClose(): void };
export default function HelpDialog({
  api,
  initialSection = "quick_start",
  onClose,
}: Props) {
  const [payload, setPayload] = useState<({ api: BackendApi; attempt: number; value: HelpPayload }) | null>(null);
  const [error, setError] = useState<({ api: BackendApi; attempt: number; message: string }) | null>(null);
  const [attempt, setAttempt] = useState(0);
  // Hide the previous API's content immediately, even before effect cleanup.
  const context = { api, attempt };
  const currentPayload = blankWorkspaceDefaultsContextIsCurrent(payload, context) ? payload!.value : null;
  const currentError = blankWorkspaceDefaultsContextIsCurrent(error, context) ? error!.message : "";
  const [releaseError, setReleaseError] = useState<({ api: BackendApi; attempt: number; message: string }) | null>(null);
  const currentReleaseError = blankWorkspaceDefaultsContextIsCurrent(releaseError, context) ? releaseError!.message : "";
  const [opening, setOpening] = useState(false);
  const openingRef = useRef(false);
  const openOnce = useRef(createExclusiveAsyncAction());
  const [section, setSection] = useState(initialSection);
  const close = () => { dismissUnlessBusy(openingRef.current, onClose); };
  const { dialogRef, titleId } = useDialogAccessibility(close);
  async function openReleases() {
    await openOnce.current(async () => {
      openingRef.current = true;
      setOpening(true);
      setReleaseError(null);
      try {
        // Help stays open after success, unlike the update prompt.
        await runReleasePageAction(() => api.open_releases_page(), () => {}, (message) => setReleaseError({ api, attempt, message }));
      } finally {
        openingRef.current = false;
        setOpening(false);
      }
    });
  }
  useEffect(() => {
    let alive = true;
    setError(null);
    setPayload(null);
    void api.get_help_sections()
      .then((value) => { if (alive) setPayload({ api, attempt, value }); })
      .catch((reason) => { if (alive) setError({ api, attempt, message: String(reason) }); });
    return () => {
      alive = false;
    };
  }, [api,attempt]);
  const current =
    currentPayload?.sections.find((x) => x.id === section) ?? currentPayload?.sections[0];
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <section
        ref={dialogRef}
        tabIndex={-1}
        className="modal-window help-window"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={opening}
      >
        <header className="modal-title">
          <strong id={titleId}>ヘルプ</strong>
          <button aria-label="閉じる" disabled={opening} onClick={close}>
            ×
          </button>
        </header>
        {currentError ? <><div className="dialog-error" role="alert">ヘルプの読込に失敗しました: {currentError}</div><div className="dialog-footer"><button onClick={close} disabled={opening}>閉じる</button><button className="primary" onClick={()=>setAttempt(value=>value+1)}>再試行</button></div></> : !currentPayload ? (
          <div className="dialog-loading" role="status">ヘルプを読み込んでいます…</div>
        ) : (
          <>
            <div className="help-header">{currentPayload.header}</div>
            <div className="help-layout">
              <nav aria-label="ヘルプ項目">
                {currentPayload.sections.map((x) => (
                  <button
                    key={x.id}
                    className={current?.id === x.id ? "active" : ""}
                    aria-current={current?.id === x.id ? "page" : undefined}
                    onClick={() => setSection(x.id)}
                  >
                    {x.title}
                  </button>
                ))}
              </nav>
              <article key={current?.id}>
                <h2>{current?.title}</h2>
                <pre>{current?.body}</pre>
              </article>
            </div>
            {currentReleaseError && <div className="dialog-error inline" role="alert">{currentReleaseError}</div>}
            <div className="dialog-footer">
              <button onClick={() => void openReleases()} disabled={opening}>
                {opening ? "開いています…" : "リリースページ"}
              </button>
              <span />
              <button className="primary" disabled={opening} onClick={close}>
                閉じる
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
