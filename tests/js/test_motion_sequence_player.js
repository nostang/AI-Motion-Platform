"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const MotionSequencePlayer = require("../../frontend/js/motion-sequence-player.js");

function harness(reducedMotion = false) {
  const callbacks = [];
  const frames = [];
  const states = [];
  const player = new MotionSequencePlayer({
    frameCount: 6,
    intervalMs: 425,
    reducedMotion,
    onFrame: (index) => frames.push(index),
    onStateChange: (playing) => states.push(playing),
    schedule: (callback) => {
      callbacks.push(callback);
      return callbacks.length - 1;
    },
    cancel: (timer) => {
      callbacks[timer] = null;
    }
  });
  const tick = () => {
    const callback = callbacks.find((candidate) => typeof candidate === "function");
    assert.ok(callback);
    callbacks[callbacks.indexOf(callback)] = null;
    callback();
  };
  return { player, frames, states, tick };
}

test("autoplay advances six frames and loops", () => {
  const { player, frames, tick } = harness();
  player.start();
  for (let index = 0; index < 6; index += 1) tick();

  assert.equal(player.isPlaying, true);
  assert.deepEqual(frames, [1, 2, 3, 4, 5, 0]);
});

test("pause stops and resume continues from current frame", () => {
  const { player, frames, tick } = harness();
  player.start();
  tick();
  player.pause();
  assert.equal(player.currentIndex, 1);
  assert.equal(player.isPlaying, false);

  player.play();
  tick();
  assert.equal(player.currentIndex, 2);
  assert.deepEqual(frames, [1, 2]);
});

test("manual selection changes frame without creating network behavior", () => {
  const { player, frames } = harness();
  player.select(4);

  assert.equal(player.currentIndex, 4);
  assert.deepEqual(frames, [4]);
});

test("reduced motion disables default autoplay but manual play remains available", () => {
  const { player, states, tick } = harness(true);
  player.start();
  assert.equal(player.isPlaying, false);
  assert.deepEqual(states, [false]);

  player.play();
  tick();
  assert.equal(player.currentIndex, 1);
  assert.equal(player.isPlaying, true);
});
