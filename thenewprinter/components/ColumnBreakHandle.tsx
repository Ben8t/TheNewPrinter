'use client';

interface Props {
  onInsert: () => void;
}

export function ColumnBreakHandle({ onInsert }: Props) {
  return (
    <button
      className="col-break-handle print-hidden"
      onClick={onInsert}
      title="Insert column break here"
    >
      ↕ column break
    </button>
  );
}
