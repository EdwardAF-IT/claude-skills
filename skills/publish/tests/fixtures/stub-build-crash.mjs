// Stand-in for magazine/scripts/build-magazine.mjs crashing outside its own catch (e.g. a
// dependency missing before build() even runs) — still exit 1, still red.
throw new Error('mmdc not found on PATH');
