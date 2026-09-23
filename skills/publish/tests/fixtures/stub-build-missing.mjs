// Stand-in for magazine/scripts/build-magazine.mjs: reports a fidelity failure in the exact
// shape the real builder prints ("build-magazine: MISSING <file>:<line>: <text>"), so the
// board's regex is proven against real output shape without needing a full mmdc render.
console.log('wrote out.html (10 KB, 1 document(s))');
console.log('kind: brief — 5 words, 1 sections, 0 figures, widest table 0 cols; single column, sans body');
console.error('build-magazine: MISSING doc.md:3: The service reads the Installer_ID field.');
console.error('build-magazine: fidelity check failed — 1 source line(s) or cell(s) not found in the edition');
process.exit(2);
