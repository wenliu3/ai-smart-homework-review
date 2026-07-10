/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/ban-types
  const component: DefineComponent<{}, {}, any>;
  export default component;
}

declare module "docx-preview" {
  export interface RenderOptions {
    className?: string;
    inWrapper?: boolean;
    ignoreWidth?: boolean;
    ignoreHeight?: boolean;
    breakPages?: boolean;
    [key: string]: any;
  }
  export function renderAsync(
    data: Blob | ArrayBuffer,
    bodyContainer: HTMLElement,
    styleContainer?: HTMLElement | null,
    options?: RenderOptions
  ): Promise<HTMLElement | void>;
}
