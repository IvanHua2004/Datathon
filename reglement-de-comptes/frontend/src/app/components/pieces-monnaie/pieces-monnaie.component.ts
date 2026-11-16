import { Component } from '@angular/core';

const DUREE_PIECE = 940;
const PIECES = [
  { x: 4, y: 16, drift: -13, spin: -36, delay: 0 },
  { x: 14, y: 4, drift: -9, spin: 29, delay: 27 },
  { x: 29, y: -1, drift: 8, spin: -58, delay: 11 },
  { x: 67, y: 2, drift: 12, spin: 31, delay: 46 },
  { x: 88, y: 8, drift: 17, spin: 69, delay: 0 },
  { x: 97, y: 26, drift: 13, spin: -32, delay: 34 },
  { x: 99, y: 44, drift: 9, spin: 52, delay: 18 },
  { x: 2, y: 47, drift: -12, spin: -44, delay: 56 },
  { x: 5, y: 68, drift: -8, spin: 33, delay: 71 },
  { x: 94, y: 73, drift: 13, spin: -41, delay: 79 },
];

export const DUREE_EFFET_PIECES = DUREE_PIECE + Math.max(...PIECES.map((piece) => piece.delay));

@Component({
  selector: 'rdc-pieces-monnaie',
  templateUrl: './pieces-monnaie.component.html',
  styleUrl: './pieces-monnaie.component.scss',
})
export class PiecesMonnaieComponent {
  readonly duree = DUREE_PIECE;
  readonly pieces = PIECES;
}
