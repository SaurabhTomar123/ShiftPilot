import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const variants = cva('button', { variants: { variant: { default: '', primary: 'primary', subtle: 'subtle' } }, defaultVariants: { variant: 'default' } });

export function Button({ className, variant, asChild = false, ...props }: React.ComponentProps<'button'> & VariantProps<typeof variants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : 'button';
  return <Component data-slot="button" className={cn(variants({ variant }), className)} {...props} />;
}
