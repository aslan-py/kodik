import type { SVGProps } from "react";

interface IconDef {
  width: number;
  height: number;
  viewBox: [number, number, number, number];
  /** SVG inner content without stroke/fill color attributes */
  inner: string;
}

const icons: Record<string, IconDef> = {
  link: {
    width: 14, height: 14, viewBox: [0, 0, 14, 14],
    inner: '<path d="M12 6V2H8M12 2L7 7M6 3H3.5C2.67157 3 2 3.67157 2 4.5V10.5C2 11.3284 2.67157 12 3.5 12H9.5C10.3284 12 11 11.3284 11 10.5V8" stroke-width="1.25" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  add: {
    width: 11, height: 11, viewBox: [0, 0, 11, 11],
    inner: '<path d="M5.25 0.75V9.75M0.75 5.25H9.75" stroke-width="1.5" stroke-linecap="round"/>',
  },
  "arrow-down": {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M5 6.5L8 9.5L11 6.5" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  calendar: {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M12 3.5H4C3.17157 3.5 2.5 4.17157 2.5 5V12C2.5 12.8284 3.17157 13.5 4 13.5H12C12.8284 13.5 13.5 12.8284 13.5 12V5C13.5 4.17157 12.8284 3.5 12 3.5Z" stroke-width="1.5"/><path d="M5 2.5V4.5M11 2.5V4.5M2.5 6.5H13.5" stroke-width="1.5" stroke-linecap="round"/>',
  },
  edit: {
    width: 12, height: 12, viewBox: [0, 0, 12, 12],
    inner: '<path d="M8.52103 0.846924L10.75 3.1175M0.75 10.6175L1.5 7.6175L7.85 1.2675C8.54 0.5775 9.66 0.5775 10.35 1.2675C11.04 1.9575 11.04 3.0775 10.35 3.7675L4 10.1175L0.75 10.6175Z" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  "arrow-right": {
    width: 11, height: 9, viewBox: [0, 0, 11, 9],
    inner: '<path d="M0.75 4.25H9.75M6.25 7.75L9.75 4.25L6.25 0.75" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  check: {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M3.5 8.25L6.5 11L12.5 4.75" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  close: {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M4 4L12 12M12 4L4 12" stroke-width="1.5" stroke-linecap="round"/>',
  },
  "open-source": {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M13 7V3H9M13 3L7.5 8.5M7 4H4.5C4.10218 4 3.72064 4.15804 3.43934 4.43934C3.15804 4.72064 3 5.10218 3 5.5V11.5C3 11.8978 3.15804 12.2794 3.43934 12.5607C3.72064 12.842 4.10218 13 4.5 13H10.5C10.8978 13 11.2794 12.842 11.5607 12.5607C11.842 12.2794 12 11.8978 12 11.5V9" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  copylink: {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<g clip-path="url(#cl-copylink)"><path d="M6.19999 9.79997L9.79999 6.19997M5.09999 11.9L4.09999 12.8C3.58187 13.2252 2.9241 13.4425 2.25463 13.4096C1.58516 13.3768 0.951846 13.096 0.477887 12.6221C0.0039275 12.1481 -0.276794 11.5148 -0.309674 10.8453C-0.342555 10.1759 -0.125242 9.5181 0.299992 8.99997L2.89999 6.39997C3.40558 5.89922 4.0884 5.61831 4.79999 5.61831C5.51159 5.61831 6.19441 5.89922 6.69999 6.39997M10.9 4.09997L11.9 3.19997C12.1391 2.90865 12.4365 2.6706 12.7732 2.50116C13.1098 2.33172 13.4782 2.23463 13.8546 2.21614C14.2311 2.19765 14.6072 2.25818 14.9588 2.39382C15.3104 2.52946 15.6298 2.73721 15.8963 3.0037C16.1628 3.2702 16.3705 3.58953 16.5061 3.94116C16.6418 4.29278 16.7023 4.66891 16.6838 5.04534C16.6653 5.42176 16.5682 5.79015 16.3988 6.12679C16.2294 6.46344 15.9913 6.76088 15.7 6.99997L13.1 9.59997C12.5944 10.1007 11.9116 10.3816 11.2 10.3816C10.4884 10.3816 9.80558 10.1007 9.29999 9.59997" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></g><defs><clipPath id="cl-copylink"><rect width="16" height="16" fill="white"/></clipPath></defs>',
  },
  search: {
    width: 16, height: 16, viewBox: [0, 0, 16, 16],
    inner: '<path d="M7 11.5C9.48528 11.5 11.5 9.48528 11.5 7C11.5 4.51472 9.48528 2.5 7 2.5C4.51472 2.5 2.5 4.51472 2.5 7C2.5 9.48528 4.51472 11.5 7 11.5Z" stroke-width="1.4"/><path d="M10.3999 10.4L13.9999 14" stroke-width="1.4" stroke-linecap="round"/>',
  },
};

export type IconName = keyof typeof icons;

export type IconProps = {
  name: IconName;
  className?: string;
} & Omit<SVGProps<SVGSVGElement>, "className" | "name">;

export function Icon({ name, className = "", ...props }: IconProps) {
  const def = icons[name];
  if (!def) return null;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={def.width}
      height={def.height}
      viewBox={def.viewBox.join(" ")}
      fill="none"
      stroke="currentColor"
      className={className}
      {...props}
      dangerouslySetInnerHTML={{ __html: def.inner }}
    />
  );
}
