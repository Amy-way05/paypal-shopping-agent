const PATHS = {
  tag: 'M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z M7.5 7.5h.01',
  shield: 'M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3z M12 8v5 M12 16h.01',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8L19 17z',
  target: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 12h.01',
  truck: 'M2 6h12v10H2z M14 10h4l3 3v3h-7z M6 19.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M17 19.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z',
  undo: 'M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M6 6l12 12 M18 6L6 18',
  send: 'M4 12l16-8-6 16-2.5-6.5L4 12z',
  plus: 'M12 5v14 M5 12h14',
  download: 'M12 4v11 M12 15l-4-4 M12 15l4-4 M5 20h14',
  bolt: 'M13 3L5 14h6l-1 7 8-11h-6l1-7z',
  lock: 'M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 0 1 7 0v3',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 11v5 M12 8h.01',
  chat: 'M4 5h16v11H9l-5 4V5z',
  external: 'M14 4h6v6 M20 4l-9 9 M18 14v5H5V6h5',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, className = 'h-5 w-5' }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
