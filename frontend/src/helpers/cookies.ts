// src/helpers/cookies.ts
// Утилиты для работы с куки (хранение JWT access-токена)

const TOKEN_KEY = "access_token";

export function getCookie(name: string): string | undefined {
  const matches = document.cookie.match(
    new RegExp(
      "(?:^|; )" +
        // eslint-disable-next-line no-useless-escape
        name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, "\\$1") +
        "=([^;]*)",
    ),
  );
  return matches ? decodeURIComponent(matches[1]) : undefined;
}

export function setCookie(
  name: string,
  value: string,
  props: { [key: string]: string | number | Date | boolean } = {},
) {
  props = {
    path: "/",
    ...props,
  };

  let exp = props.expires;
  if (exp && typeof exp === "number") {
    const d = new Date();
    d.setTime(d.getTime() + exp * 1000);
    exp = props.expires = d;
  }

  if (exp && exp instanceof Date) {
    props.expires = exp.toUTCString();
  }
  value = encodeURIComponent(value);
  let updatedCookie = name + "=" + value;
  for (const propName in props) {
    updatedCookie += "; " + propName;
    const propValue = props[propName];
    if (propValue !== true) {
      updatedCookie += "=" + propValue;
    }
  }
  document.cookie = updatedCookie;
}

export function deleteCookie(name: string) {
  setCookie(name, "", { expires: -1 });
}

// --- Специфичные для JWT access-токена ---

export function setAccessToken(token: string) {
  setCookie(TOKEN_KEY, token, {
    path: "/",
    sameSite: "lax",
    // secure: true, // включить при работе по HTTPS
  });
}

export function getAccessToken(): string | undefined {
  return getCookie(TOKEN_KEY);
}

export function clearAccessToken() {
  deleteCookie(TOKEN_KEY);
}
