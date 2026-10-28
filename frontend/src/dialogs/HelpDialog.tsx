import { useEffect, useState } from "react";
import type { BackendApi, HelpPayload } from "./bridge";
import { useDialogAccessibility } from "./useDialogAccessibility";
type Props = { api: BackendApi; initialSection?: string; onClose(): void };
export default function HelpDialog({
  api,
  initialSection = "quick_start",
  onClose,
}: Props) {
  const [payload, setPayload] = useState<HelpPayload | null>(null);
  const [error,setError]=useState(""),[attempt,setAttempt]=useState(0);
  const [section, setSection] = useState(initialSection),
    { dialogRef, titleId } = useDialogAccessibility(onClose);
  useEffect(() => {
    let alive = true;
    setError("");
    void api.get_help_sections().then((x) => alive && setPayload(x)).catch(reason=>alive&&setError(String(reason)));
    return () => {
      alive = false;
    };
  }, [api,attempt]);
  const current =
    payload?.sections.find((x) => x.id === section) ?? payload?.sections[0];
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <section
        ref={dialogRef}
        tabIndex={-1}
        className="modal-window help-window"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="modal-title">
          <strong id={titleId}>ヘルプ</strong>
          <button aria-label="閉じる" onClick={onClose}>
            ×
          </button>
        </header>
        {error ? <><div className="dialog-error">ヘルプの読込に失敗しました: {error}</div><div className="dialog-footer"><button onClick={onClose}>閉じる</button><button className="primary" onClick={()=>setAttempt(value=>value+1)}>再試行</button></div></> : !payload ? (
          <div className="dialog-loading">ヘルプを読み込んでいます…</div>
        ) : (
          <>
            <div className="help-header">{payload.header}</div>
            <div className="help-layout">
              <nav aria-label="ヘルプ項目">
                {payload.sections.map((x) => (
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
              <article>
                <h2>{current?.title}</h2>
                <pre>{current?.body}</pre>
              </article>
            </div>
            <div className="dialog-footer">
              <button onClick={() => void api.open_releases_page()}>
                リリースページ
              </button>
              <span />
              <button className="primary" onClick={onClose}>
                閉じる
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
