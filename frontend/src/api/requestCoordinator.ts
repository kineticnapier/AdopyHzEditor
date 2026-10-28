export class LatestRequestGate {
  private generation = 0;

  issue(): number {
    this.generation += 1;
    return this.generation;
  }

  invalidate(): void {
    this.generation += 1;
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation;
  }
}

export class SerialTaskQueue {
  private tail: Promise<unknown> = Promise.resolve();

  enqueue<T>(task: () => Promise<T>): Promise<T> {
    const result = this.tail.then(task, task);
    this.tail = result.then(
      () => undefined,
      () => undefined,
    );
    return result;
  }
}

export function enqueueAppliedTask<T>(
  queue: SerialTaskQueue,
  call: () => Promise<T>,
  apply: (result: T) => void,
  isCurrent: () => boolean = () => true,
): Promise<T | undefined> {
  return queue.enqueue(async () => {
    // A queued task must not mutate a document that replaced its origin.
    if (!isCurrent()) return undefined;
    const result = await call();
    // An in-flight response can also outlive a document switch.
    if (isCurrent()) apply(result);
    return result;
  });
}

export async function runWithErrorFeedback<T>(
  task:()=>Promise<T>,
  onSuccess:(value:T)=>void,
  onError:(message:string)=>void,
):Promise<T|undefined>{
  try{const value=await task();onSuccess(value);return value}
  catch(error){onError(String(error));return undefined}
}

export class AsyncActionGuard{
  private running=false;
  get isRunning(){return this.running}
  async run(action:()=>Promise<void>):Promise<boolean>{
    if(this.running)return false;
    this.running=true;
    try{await action();return true}finally{this.running=false}
  }
}

/** Serialize a document-wide action and its state application with note edits. */
export function enqueueStateTask<T>(
  queue: SerialTaskQueue,
  call: () => Promise<T>,
  apply: (state: T) => void,
): Promise<T> {
  return queue.enqueue(async () => {
    const state = await call();
    apply(state);
    return state;
  });
}
