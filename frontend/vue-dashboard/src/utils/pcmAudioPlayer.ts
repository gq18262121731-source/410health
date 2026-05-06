export interface PcmAudioPlayerState {
  supported: boolean;
  level: number;
  queuedMs: number;
  droppedBacklogCount: number;
}

export class PcmAudioPlayer {
  private context: AudioContext | null = null;
  private gainNode: GainNode | null = null;
  private nextPlaybackTime = 0;
  private sampleRate = 8000;
  private lastLevel = 0;
  private droppedBacklogCount = 0;
  private listeners = new Set<(state: PcmAudioPlayerState) => void>();
  private decayTimer: number | undefined;

  get supported() {
    return typeof window !== "undefined" && typeof window.AudioContext !== "undefined";
  }

  async start(sampleRate: number) {
    if (!this.supported) {
      throw new Error("This browser does not support realtime PCM playback.");
    }

    this.sampleRate = sampleRate > 0 ? sampleRate : 8000;
    if (!this.context) {
      this.context = new window.AudioContext({
        latencyHint: "interactive",
        sampleRate: this.sampleRate,
      });
      this.gainNode = this.context.createGain();
      this.gainNode.gain.value = 1;
      this.gainNode.connect(this.context.destination);
    }

    if (this.context.state === "suspended") {
      await this.context.resume();
    }
    this.nextPlaybackTime = this.context.currentTime + 0.08;
    this.startDecayTimer();
    this.emitState();
  }

  stop() {
    if (this.decayTimer !== undefined) {
      window.clearInterval(this.decayTimer);
      this.decayTimer = undefined;
    }
    this.nextPlaybackTime = 0;
    this.lastLevel = 0;
    this.emitState();
  }

  async dispose() {
    this.stop();
    if (this.context) {
      await this.context.close();
      this.context = null;
      this.gainNode = null;
    }
  }

  onState(listener: (state: PcmAudioPlayerState) => void) {
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  pushChunk(chunk: ArrayBuffer | Uint8Array) {
    if (!this.context || !this.gainNode) return;

    const bytes = chunk instanceof Uint8Array ? chunk : new Uint8Array(chunk);
    if (bytes.byteLength < 2) return;

    const sampleCount = Math.floor(bytes.byteLength / 2);
    const pcm = new Int16Array(bytes.buffer, bytes.byteOffset, sampleCount);
    const buffer = this.context.createBuffer(1, sampleCount, this.sampleRate);
    const channel = buffer.getChannelData(0);

    let peak = 0;
    for (let index = 0; index < sampleCount; index += 1) {
      const value = pcm[index] / 32768;
      channel[index] = value;
      const amplitude = Math.abs(value);
      if (amplitude > peak) peak = amplitude;
    }

    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gainNode);

    const now = this.context.currentTime;
    const queuedAhead = Math.max(0, this.nextPlaybackTime - now);
    if (queuedAhead > 0.75) {
      this.nextPlaybackTime = now + 0.12;
      this.droppedBacklogCount += 1;
    }

    const startAt = Math.max(now + 0.02, this.nextPlaybackTime);
    source.start(startAt);
    this.nextPlaybackTime = startAt + buffer.duration;
    this.lastLevel = Math.max(peak * 100, this.lastLevel * 0.65);
    this.emitState();
  }

  private getState(): PcmAudioPlayerState {
    const queuedMs =
      this.context && this.nextPlaybackTime > 0
        ? Math.max(0, this.nextPlaybackTime - this.context.currentTime) * 1000
        : 0;
    return {
      supported: this.supported,
      level: Number(this.lastLevel.toFixed(1)),
      queuedMs: Number(queuedMs.toFixed(1)),
      droppedBacklogCount: this.droppedBacklogCount,
    };
  }

  private emitState() {
    const state = this.getState();
    for (const listener of this.listeners) listener(state);
  }

  private startDecayTimer() {
    if (this.decayTimer !== undefined) return;
    this.decayTimer = window.setInterval(() => {
      if (this.lastLevel <= 0.4) this.lastLevel = 0;
      else this.lastLevel *= 0.82;
      this.emitState();
    }, 120);
  }
}
