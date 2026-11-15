import { useEffect, useId, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

export function UserMessageText({ content }: { content: string }) {
  const id = useId();
  const text = useRef<HTMLDivElement>(null);
  const [canCollapse, setCanCollapse] = useState(false);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const node = text.current;
    if (!node) return;
    const measure = () => {
      const lineHeight = Number.parseFloat(getComputedStyle(node).lineHeight);
      setCanCollapse(node.scrollHeight > lineHeight * 10 + 1);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [content]);

  return (
    <>
      <div id={id} className={canCollapse && !expanded ? "user-message-clipped" : undefined}>
        <div ref={text} className="whitespace-pre-wrap break-words leading-relaxed">
          {content}
        </div>
      </div>
      {canCollapse && (
        <button
          type="button"
          className="user-message-toggle"
          aria-expanded={expanded}
          aria-controls={id}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Tampilkan lebih sedikit" : "Tampilkan lebih banyak"}
          <ChevronDown size={15} aria-hidden="true" />
        </button>
      )}
    </>
  );
}
