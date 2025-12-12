import type { TextareaHTMLAttributes } from 'react'
import { useId } from 'react'

export interface TextareaProps extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'onChange'> {
  value: string
  onChange: (value: string) => void
  label?: string
  rows?: number
}

export function Textarea({
  value,
  onChange,
  label,
  rows = 4,
  placeholder,
  disabled,
  className,
  ...props
}: TextareaProps) {
  const id = useId()

  const baseClasses = `
    w-full px-4 py-3 border border-slate-600 rounded-lg
    bg-slate-700/50 text-white placeholder-slate-400
    focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500
    disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed resize-y
    transition-all duration-200
  `

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-slate-300 mb-2">
          {label}
        </label>
      )}
      <textarea
        id={id}
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        disabled={disabled}
        className={`${baseClasses} ${className || ''}`}
        {...props}
      />
    </div>
  )
}
