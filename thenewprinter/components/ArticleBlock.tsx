'use client';

import { useState } from 'react';
import { ColumnBreakHandle } from './ColumnBreakHandle';
import { LIST_ITEM_GAP_PX, LIST_BLOCK_PADDING_PX, CODE_BLOCK_PADDING_PX } from '@/lib/layout-engine';
import type { RenderedBlock } from '@/lib/types';

interface Props {
  rendered: RenderedBlock;
  onInsertBreakAfter: () => void;
  onRemoveImage?: () => void;
}

export function ArticleBlock({ rendered, onInsertBreakAfter, onRemoveImage }: Props) {
  const [hovered, setHovered] = useState(false);
  const { block, lines, lineHeight } = rendered;

  if (block.type === 'image') {
    return (
      <div
        className="block block-image"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={block.src} alt={block.alt} style={{ maxWidth: '100%', height: 'auto' }} />
        {hovered && (
          <div className="image-overlay print-hidden">
            {onRemoveImage && (
              <button className="img-remove-btn" onClick={onRemoveImage} title="Remove this image">
                Remove image
              </button>
            )}
            <ColumnBreakHandle onInsert={onInsertBreakAfter} />
          </div>
        )}
      </div>
    );
  }

  if (block.type === 'code') {
    return (
      <div
        className="block block-code"
        style={{ paddingTop: CODE_BLOCK_PADDING_PX, paddingBottom: CODE_BLOCK_PADDING_PX }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {lines.map((line, i) => (
          <div key={i} className="code-line" style={{ lineHeight: `${lineHeight}px`, whiteSpace: 'pre' }}>
            {line || '\u00A0'}
          </div>
        ))}
        {hovered && <ColumnBreakHandle onInsert={onInsertBreakAfter} />}
      </div>
    );
  }

  if (block.type === 'list') {
    return (
      <div
        className="block block-list"
        style={{ paddingTop: LIST_BLOCK_PADDING_PX, paddingBottom: LIST_BLOCK_PADDING_PX }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {lines.map((line, i) =>
          line === '' ? (
            <div key={i} style={{ height: LIST_ITEM_GAP_PX }} />
          ) : (
            <div key={i} className="text-line" style={{ lineHeight: `${lineHeight}px`, whiteSpace: 'pre' }}>
              {line}
            </div>
          )
        )}
        {hovered && <ColumnBreakHandle onInsert={onInsertBreakAfter} />}
      </div>
    );
  }

  const headingLevel =
    block.type === 'heading' ? (`h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4') : null;
  const blockClass =
    block.type === 'heading'
      ? `block block-heading level-${block.level}`
      : `block block-${block.type}`;

  return (
    <div
      className={blockClass}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {headingLevel
        ? lines.map((line, i) => {
            const Tag = headingLevel;
            return (
              <Tag key={i} className="text-line" style={{ lineHeight: `${lineHeight}px`, whiteSpace: 'pre', margin: 0 }}>
                {line}
              </Tag>
            );
          })
        : lines.map((line, i) => (
            <div key={i} className="text-line" style={{ lineHeight: `${lineHeight}px`, whiteSpace: 'pre' }}>
              {line}
            </div>
          ))}
      {hovered && <ColumnBreakHandle onInsert={onInsertBreakAfter} />}
    </div>
  );
}
