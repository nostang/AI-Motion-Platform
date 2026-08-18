(function (root, factory) {
  "use strict";
  const MotionSequencePlayer = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = MotionSequencePlayer;
  } else {
    root.MotionSequencePlayer = MotionSequencePlayer;
  }
})(typeof window !== "undefined" ? window : globalThis, function () {
  "use strict";

  return class MotionSequencePlayer {
    constructor({
      frameCount,
      intervalMs,
      reducedMotion = false,
      onFrame,
      onStateChange,
      schedule = (callback, delay) => window.setTimeout(callback, delay),
      cancel = (timer) => window.clearTimeout(timer)
    }) {
      if (!Number.isInteger(frameCount) || frameCount < 1) {
        throw new Error("frameCount must be a positive integer");
      }
      this.frameCount = frameCount;
      this.intervalMs = intervalMs;
      this.reducedMotion = reducedMotion;
      this.onFrame = onFrame;
      this.onStateChange = onStateChange;
      this.schedule = schedule;
      this.cancel = cancel;
      this.currentIndex = 0;
      this.isPlaying = false;
      this.timer = null;
    }

    start() {
      if (this.reducedMotion) {
        this.onStateChange?.(false);
        return;
      }
      this.play();
    }

    play() {
      if (this.isPlaying) return;
      this.isPlaying = true;
      this.onStateChange?.(true);
      this.#scheduleNext();
    }

    pause() {
      if (this.timer !== null) this.cancel(this.timer);
      this.timer = null;
      this.isPlaying = false;
      this.onStateChange?.(false);
    }

    select(index) {
      if (!Number.isInteger(index) || index < 0 || index >= this.frameCount) {
        return;
      }
      this.currentIndex = index;
      this.onFrame?.(this.currentIndex);
      if (this.isPlaying) {
        if (this.timer !== null) this.cancel(this.timer);
        this.#scheduleNext();
      }
    }

    advance() {
      this.timer = null;
      this.currentIndex = (this.currentIndex + 1) % this.frameCount;
      this.onFrame?.(this.currentIndex);
      if (this.isPlaying) this.#scheduleNext();
    }

    destroy() {
      this.pause();
      this.onFrame = null;
      this.onStateChange = null;
    }

    #scheduleNext() {
      this.timer = this.schedule(() => this.advance(), this.intervalMs);
    }
  };
});
