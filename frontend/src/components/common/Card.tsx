import type { ReactNode } from 'react'

export interface CardProps {
  title?: string
  children: ReactNode
  className?: string
  /** Optional action element to display in the card header (right side) */
  headerAction?: ReactNode
}

export function Card({ title, children, className = '', headerAction }: CardProps) {
  return (
    <div className={`bg-slate-800/50 rounded-xl border border-slate-700 overflow-hidden ${className}`}>
      {title && (
        <div className="px-6 py-4 border-b border-slate-700 bg-slate-800/30 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          {headerAction}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  )
}
