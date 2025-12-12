import type { InputHTMLAttributes } from 'react'
import { useId } from 'react'

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  value: string
  onChange: (value: string) => void
  label?: string
}

export function Input({ value, onChange, label, required, disabled, ...props }: InputProps) {
  const id = useId()

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-slate-300 mb-2">
          {label}
          {required && <span className="text-cyan-400 ml-1">*</span>}
        </label>
      )}
      <input
        id={id}
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        required={required}
        disabled={disabled}
        className={`
          w-full px-4 py-3 border border-slate-600 rounded-lg
          bg-slate-700/50 text-white placeholder-slate-400
          focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500
          disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed
          transition-all duration-200
        `}
        {...props}
      />
    </div>
  )
}
