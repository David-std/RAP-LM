// Long-form documentation layout shared by the Model and Methodology views:
// a sticky table of contents, numbered sections, captioned figures and tables.

import { useEffect, useRef, useState, type ReactNode } from "react";

export interface DocSection {
  id: string;
  title: string;
  body: ReactNode;
}

export function DocPage({ title, lead, meta, sections }: { title: string; lead: ReactNode; meta?: ReactNode; sections: DocSection[] }) {
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(sections[0]?.id);

  useEffect(() => {
    const container = root.current;
    if (!container) return;
    const nodes = sections.map((s) => container.querySelector<HTMLElement>(`#${s.id}`)).filter((n): n is HTMLElement => !!n);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { root: container, rootMargin: "0px 0px -70% 0px" },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [sections]);

  const go = (id: string) => {
    root.current?.querySelector(`#${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(id);
  };

  return (
    <div className="page doc-page" ref={root}>
      <div className="doc">
        <nav className="doc-toc" aria-label="Contenido de la página">
          <p className="doc-toc-title">Contenido</p>
          <ol>
            {sections.map((s, i) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  aria-current={active === s.id ? "location" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    go(s.id);
                  }}
                >
                  <span className="doc-num">{i + 1}</span>
                  {s.title}
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <article className="doc-body">
          <header className="doc-head">
            <h1>{title}</h1>
            <p className="doc-lead">{lead}</p>
            {meta && <p className="doc-meta">{meta}</p>}
          </header>
          {sections.map((s, i) => (
            <section key={s.id} id={s.id} className="doc-section" aria-labelledby={`${s.id}-h`}>
              <h2 id={`${s.id}-h`}>
                <span className="doc-num">{i + 1}</span>
                {s.title}
              </h2>
              {s.body}
            </section>
          ))}
        </article>
      </div>
    </div>
  );
}

/** Public repository; every cited file is versioned there. */
export const REPO = "https://github.com/David-std2/RAP-LM/blob/main/";

/** "Fuente:" line with links to the repository files a table or figure comes from. */
export function Source({ files, children }: { files?: string[]; children?: ReactNode }) {
  return (
    <p className="doc-source">
      Fuente: {children}
      {children && files?.length ? "; " : ""}
      {files?.map((f, i) => (
        <span key={f}>
          {i > 0 && ", "}
          <a href={REPO + f} target="_blank" rel="noreferrer"><code>{f}</code></a>
        </span>
      ))}
      .
    </p>
  );
}

export function Figure({ n, caption, children, wide, source }: { n: number; caption: ReactNode; children: ReactNode; wide?: boolean; source?: ReactNode }) {
  return (
    <figure className={wide ? "doc-figure wide" : "doc-figure"}>
      {children}
      <figcaption>
        <b>Figura {n}.</b> {caption}
      </figcaption>
      {source}
    </figure>
  );
}

export function DocTable({ n, caption, children, note, wide, source }: { n: number; caption: ReactNode; children: ReactNode; note?: ReactNode; wide?: boolean; source?: ReactNode }) {
  return (
    <div className={wide ? "doc-table wide" : "doc-table"}>
      <p className="doc-table-caption">
        <b>Tabla {n}.</b> {caption}
      </p>
      <div className="doc-table-scroll">
        <table>{children}</table>
      </div>
      {note && <p className="doc-table-note">{note}</p>}
      {source}
    </div>
  );
}
