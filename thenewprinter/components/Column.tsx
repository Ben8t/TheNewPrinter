'use client';

import { ArticleBlock } from './ArticleBlock';
import type { ColumnContent } from '@/lib/types';

interface Props {
  content: ColumnContent;
  onInsertBreak: (blockIdx: number) => void;
  onRemoveImage: (blockIdx: number) => void;
}

export function Column({ content, onInsertBreak, onRemoveImage }: Props) {
  return (
    <div className="column">
      {content.blocks.map((rb) => (
        <ArticleBlock
          key={`${rb.blockIndex}-${rb.lines.join('').slice(0, 20)}`}
          rendered={rb}
          onInsertBreakAfter={() => onInsertBreak(rb.blockIndex)}
          onRemoveImage={rb.block.type === 'image' ? () => onRemoveImage(rb.blockIndex) : undefined}
        />
      ))}
    </div>
  );
}
