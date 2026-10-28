type MidiExportResult = { status: string };

export async function runMidiExport(
  action: () => Promise<MidiExportResult>,
  setStatus: (status: string) => void,
): Promise<void> {
  try {
    const result = await action();
    setStatus(result.status);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    setStatus(`MIDI出力に失敗しました: ${detail}`);
  }
}
