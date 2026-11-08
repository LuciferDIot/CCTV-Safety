'use client'

import React from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'primary' | 'secondary' | 'outline' | 'ghost' | 'icon' | 'reopen'
  size?: 'sm' | 'md' | 'lg'
  children?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = '', variant = 'default', size = 'md', children, ...props }, ref) => {
    let variantClass = ''
    switch (variant) {
      case 'primary':
        variantClass = 'primary-upload-btn'
        break
      case 'secondary':
        variantClass = 'secondary-sample-btn'
        break
      case 'reopen':
        variantClass = 'reopen-drawer'
        break
      case 'icon':
        variantClass = 'icon-button'
        break
      case 'outline':
        variantClass = 'border border-[#26303c] bg-[#111720] text-[#b8c7d8] hover:bg-[#1c2733] hover:text-white'
        break
      case 'ghost':
        variantClass = 'bg-transparent hover:bg-[#1c2733] text-[#8b99ab]'
        break
      default:
        variantClass = 'bg-[#111720] text-[#cdd7e4] border border-[#26303c] hover:bg-[#1a2330]'
    }

    return (
      <button
        ref={ref}
        className={`${variantClass} ${className}`.trim()}
        {...props}
      >
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
