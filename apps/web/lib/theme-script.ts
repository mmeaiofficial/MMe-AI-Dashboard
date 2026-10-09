export const THEME_KEY = "mme-theme";

/** Runs in <head> before first paint so the page never flashes the wrong theme. Keep in sync with apply(). */
export const themeScript = `(function(){try{var m=localStorage.getItem("${THEME_KEY}")||"system";var d=m==="dark"||(m==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.dataset.theme=d?"dark":"light"}catch(e){}})()`;
