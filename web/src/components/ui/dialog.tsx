"use client";

import { forwardRef } from "react";
import type { ComponentPropsWithoutRef, ElementRef, HTMLAttributes } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { cn } from "@/lib/cn";

/**
 * Hearth dialog — Radix Dialog on Hearth tokens. Radix supplies the focus trap,
 * Escape-to-close, scroll lock and ARIA wiring the QA a11y baseline depends on
 * (ADR-0035); we only restyle. Used by the cart drawer / checkout confirm.
 */
export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogClose = DialogPrimitive.Close;

export const DialogOverlay = forwardRef<
  ElementRef<typeof DialogPrimitive.Overlay>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-n-900/50 backdrop-blur-sm " +
        "transition-opacity duration-200 " +
        "data-[state=closed]:opacity-0 data-[state=open]:opacity-100 " +
        "motion-reduce:transition-none",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

export const DialogContent = forwardRef<
  ElementRef<typeof DialogPrimitive.Content>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid w-full max-w-lg -translate-x-1/2 " +
          "-translate-y-1/2 gap-4 rounded-2xl border border-border bg-surface " +
          "p-6 shadow-xl focus:outline-none " +
          "transition-opacity duration-200 " +
          "data-[state=closed]:opacity-0 data-[state=open]:opacity-100 " +
          "motion-reduce:transition-none",
        className,
      )}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

export function DialogHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div className={cn("flex flex-col gap-1.5 text-left", className)} {...props} />
  );
}

export function DialogFooter({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>): JSX.Element {
  return (
    <div
      className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}

export const DialogTitle = forwardRef<
  ElementRef<typeof DialogPrimitive.Title>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      "font-display text-h3 font-semibold leading-tight tracking-tight text-text",
      className,
    )}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

export const DialogDescription = forwardRef<
  ElementRef<typeof DialogPrimitive.Description>,
  ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-small text-text-muted", className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;
