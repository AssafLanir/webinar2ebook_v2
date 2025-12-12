import { Listbox, ListboxButton, ListboxOption, ListboxOptions } from '@headlessui/react'
import { useId } from 'react'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectProps {
  value: string
  onChange: (value: string) => void
  options: SelectOption[]
  label?: string
  disabled?: boolean
}

export function Select({ value, onChange, options, label, disabled }: SelectProps) {
  const id = useId()
  const selectedOption = options.find(opt => opt.value === value)

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-slate-300 mb-2">
          {label}
        </label>
      )}
      <Listbox value={value} onChange={onChange} disabled={disabled}>
        <div className="relative">
          <ListboxButton
            id={id}
            className={`
              relative w-full cursor-pointer rounded-lg bg-slate-700/50 py-3 pl-4 pr-10 text-left text-white
              border border-slate-600
              focus:outline-none focus:ring-2 focus:ring-cyan-500/50 focus:border-cyan-500
              disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed
              transition-all duration-200
            `}
          >
            <span className="block truncate">{selectedOption?.label || 'Select...'}</span>
            <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3">
              <svg
                className="h-5 w-5 text-slate-400"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </span>
          </ListboxButton>
          <ListboxOptions
            className={`
              absolute z-10 mt-2 max-h-60 w-full overflow-auto rounded-lg bg-slate-800 py-2
              text-base shadow-lg ring-1 ring-slate-700 focus:outline-none
            `}
          >
            {options.map(option => (
              <ListboxOption
                key={option.value}
                value={option.value}
                className={({ active, selected }) =>
                  `relative cursor-pointer select-none py-2.5 pl-4 pr-9 mx-1 rounded-md transition-colors ${
                    active ? 'bg-slate-700 text-cyan-400' : 'text-slate-200'
                  } ${selected ? 'font-medium' : ''}`
                }
              >
                {({ selected, active }) => (
                  <>
                    <span className={`block truncate ${selected ? 'font-medium' : 'font-normal'}`}>
                      {option.label}
                    </span>
                    {selected && (
                      <span className={`absolute inset-y-0 right-0 flex items-center pr-3 ${active ? 'text-cyan-400' : 'text-cyan-500'}`}>
                        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path
                            fillRule="evenodd"
                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </span>
                    )}
                  </>
                )}
              </ListboxOption>
            ))}
          </ListboxOptions>
        </div>
      </Listbox>
    </div>
  )
}
