"use client";

import { useCallback, useRef, useState } from "react";

interface Props {
  onResize: (delta: number) => void;
}

export default function ResizeHandle({ onResize }: Props) {
  const startX = useRef(0);
  const isDragging = useRef(false);
  const [active, setActive] = useState(false);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      startX.current = e.clientX;
      isDragging.current = true;
      setActive(true);

      const onMove = (ev: MouseEvent) => {
        if (!isDragging.current) return;
        const delta = ev.clientX - startX.current;
        startX.current = ev.clientX;
        onResize(delta);
      };

      const onUp = () => {
        isDragging.current = false;
        setActive(false);
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [onResize],
  );

  return (
    <div
      className="w-[3px] cursor-col-resize flex-shrink-0 relative group"
      onMouseDown={handleMouseDown}
    >
      <div
        className="absolute inset-0 transition-all duration-150"
        style={{
          background: active ? "var(--accent)" : "var(--border)",
          opacity: active ? 0.8 : 1,
        }}
      />
      <div
        className="absolute inset-y-0 -left-1 -right-1 group-hover:bg-[var(--accent)] transition-colors duration-150"
        style={{ opacity: 0.15, borderRadius: 2 }}
      />
    </div>
  );
}
