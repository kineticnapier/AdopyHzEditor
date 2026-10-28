const noteNames=["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"] as const;

export function midiToHz(midi:number){
  return 440*2**((midi-69)/12);
}

export function midiLabel(midi:number){
  const rounded=Math.round(midi),index=((rounded%12)+12)%12;
  return `${noteNames[index]}${Math.floor(rounded/12)-1}`;
}
