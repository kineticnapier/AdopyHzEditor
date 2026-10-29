/** Keep the Quick Hz preview and the chart write bound to the same form settings. */
export function quickHzActionPolicy(appending: boolean, hasChart: boolean, previewCurrent: boolean) {
  return {
    canEdit: !appending,
    canChooseChart: !appending,
    canAppend: !appending && hasChart && previewCurrent,
    canOutput: !appending && previewCurrent,
    canClose: !appending,
  };
}
