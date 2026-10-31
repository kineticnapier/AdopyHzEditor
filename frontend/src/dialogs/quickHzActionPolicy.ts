/** Lock Quick Hz settings and actions while either the chart picker or append is pending. */
export function quickHzActionPolicy(busy: boolean, hasChart: boolean, previewCurrent: boolean) {
  return {
    canEdit: !busy,
    canChooseChart: !busy,
    canAppend: !busy && hasChart && previewCurrent,
    canOutput: !busy && previewCurrent,
    canClose: !busy,
  };
}
