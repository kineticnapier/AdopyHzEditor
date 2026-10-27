import { useEffect, useId, useRef } from "react";

const focusableSelector = [
  "button:not(:disabled)",
  "input:not(:disabled)",
  "select:not(:disabled)",
  "textarea:not(:disabled)",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function useDialogAccessibility(onClose:()=>void){
  const dialogRef=useRef<HTMLElement>(null),titleId=useId(),closeRef=useRef(onClose);
  closeRef.current=onClose;
  useEffect(()=>{
    const previous=document.activeElement instanceof HTMLElement?document.activeElement:null;
    const dialog=dialogRef.current;
    window.requestAnimationFrame(()=>dialog?.querySelector<HTMLElement>(focusableSelector)?.focus());
    const key=(event:KeyboardEvent)=>{
      if(event.key==="Escape"){event.preventDefault();closeRef.current();return}
      if(event.key!=="Tab"||!dialog)return;
      const items=Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector));
      if(!items.length){event.preventDefault();dialog.focus();return}
      const first=items[0],last=items[items.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
    };
    window.addEventListener("keydown",key);
    return()=>{window.removeEventListener("keydown",key);previous?.focus()};
  },[]);
  return{dialogRef,titleId};
}
