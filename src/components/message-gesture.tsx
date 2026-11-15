import { useEffect, useRef, useState, type ReactNode } from "react";
import { CornerUpLeft } from "lucide-react";

export function MessageGesture({
  children,
  onReply,
  onMenu,
}: {
  children: ReactNode;
  onReply: () => void;
  onMenu: () => void;
}) {
  const gesture = useRef<{
    id: number;
    x: number;
    y: number;
    timer: ReturnType<typeof setTimeout>;
    dx: number;
    consumed: boolean;
  } | null>(null);
  const cancelClick = useRef(false);
  const [dx, setDx] = useState(0);
  useEffect(
    () => () => {
      if (gesture.current) clearTimeout(gesture.current.timer);
    },
    [],
  );

  function finish(commit: boolean) {
    const current = gesture.current;
    if (!current) return;
    clearTimeout(current.timer);
    gesture.current = null;
    setDx(0);
    if (current.consumed || current.dx > 8) cancelClick.current = true;
    if (commit && !current.consumed && current.dx >= 54) onReply();
  }

  return (
    <div
      className="message-gesture"
      onPointerDown={(e) => {
        cancelClick.current = false;
        if (
          e.pointerType === "mouse" ||
          !e.isPrimary ||
          (e.target as HTMLElement).closest("button,a,input")
        )
          return;
        if (gesture.current) finish(false);
        const timer = setTimeout(() => {
          if (!gesture.current) return;
          gesture.current.consumed = true;
          cancelClick.current = true;
          onMenu();
        }, 500);
        gesture.current = {
          id: e.pointerId,
          x: e.clientX,
          y: e.clientY,
          timer,
          dx: 0,
          consumed: false,
        };
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        const g = gesture.current;
        if (!g || g.id !== e.pointerId || g.consumed) return;
        const x = e.clientX - g.x,
          y = e.clientY - g.y;
        if (Math.abs(x) < 8 && Math.abs(y) < 8) return;
        clearTimeout(g.timer);
        if (Math.abs(y) > Math.abs(x) || x < 0) {
          finish(false);
          return;
        }
        g.dx = Math.min(78, x);
        setDx(g.dx);
      }}
      onPointerUp={() => finish(true)}
      onPointerCancel={() => finish(false)}
      onClickCapture={(e) => {
        if (cancelClick.current) {
          e.stopPropagation();
          e.preventDefault();
          cancelClick.current = false;
        }
      }}
      onContextMenu={(e) => {
        e.preventDefault();
        if ((e.target as HTMLElement).closest("button,a") || cancelClick.current) return;
        const current = gesture.current;
        if (current) {
          if (current.dx || current.consumed) return;
          clearTimeout(current.timer);
          current.consumed = true;
          cancelClick.current = true;
        }
        onMenu();
      }}
    >
      {dx > 8 && <CornerUpLeft className="message-gesture-arrow" size={19} aria-hidden="true" />}
      <div
        className="message-gesture-content"
        style={{ transform: dx ? `translateX(${dx}px)` : undefined }}
      >
        {children}
      </div>
    </div>
  );
}
