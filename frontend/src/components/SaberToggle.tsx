export type Theme = 'jedi' | 'sith'

/** A lightsaber hilt: click to retract the blade and re-ignite it in the other color. */
export function SaberToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const next = theme === 'jedi' ? 'Sith' : 'Jedi'
  return (
    <button
      className={`saber saber--${theme}`}
      onClick={onToggle}
      aria-label={`Switch to ${next} mode (${next === 'Sith' ? 'dark' : 'light'})`}
      title={`Switch to ${next} mode`}
    >
      <span className="saber__label">{theme === 'jedi' ? 'Jedi' : 'Sith'}</span>
      <span className="saber__hilt" aria-hidden>
        <i /><i /><i />
      </span>
      <span className="saber__blade" aria-hidden key={theme} />
    </button>
  )
}
