// Stand-in for magazine/scripts/build-magazine.mjs: reports a label-floor warning in the real
// builder's exact wording, so the board's floor-ticket regex and its shared LABEL_FLOOR_PT are
// both proven against real output shape.
console.log('wrote out.html (10 KB, 1 document(s))');
console.log('kind: brief — 5 words, 1 sections, 1 figures, widest table 0 cols; single column, sans body');
console.log('figure 1: flowchart 3.0x2.0in (native 300x200), labels 5.2pt');
console.error('build-magazine: WARNING figure 1: labels print at 5.2pt even as a portrait plate in either direction (native 300x200); the diagram needs fewer nodes per rank or shorter labels to reach 7pt');
console.error('build-magazine: 1 warning(s) — review the edition before shipping it');
console.log('fidelity: every source line and table cell is present in the edition');
process.exit(0);
