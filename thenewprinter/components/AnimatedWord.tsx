'use client';

import { useState, useEffect } from 'react';

const WORDS = ['any article', 'any essay', 'any interview', 'any long-read', 'any story'];

export function AnimatedWord() {
  const [index,   setIndex]   = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      const t = setTimeout(() => {
        setIndex((i) => (i + 1) % WORDS.length);
        setVisible(true);
      }, 380);
      return () => clearTimeout(t);
    }, 2600);
    return () => clearInterval(interval);
  }, []);

  return (
    <span
      style={{
        display: 'inline-block',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0px)' : 'translateY(-7px)',
        transition: 'opacity 0.38s cubic-bezier(0.16,1,0.3,1), transform 0.38s cubic-bezier(0.16,1,0.3,1)',
        willChange: 'transform, opacity',
      }}
    >
      {WORDS[index]}
    </span>
  );
}
