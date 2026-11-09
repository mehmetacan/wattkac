// WattKaç: statik site (site/) önünde küçük yönlendirici.
// wattkac.xyz, www.wattkac.xyz ve www.wattkac.com → https://wattkac.com (301, yol ve sorgu korunur).
// Diğer tüm istekler (wattkac.com, workers.dev) doğrudan statik dosyalardan sunulur.
const ANA = "wattkac.com";
const YONLENDIR = new Set(["www.wattkac.com", "wattkac.xyz", "www.wattkac.xyz"]);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (YONLENDIR.has(url.hostname)) {
      url.protocol = "https:";
      url.hostname = ANA;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }
    return env.ASSETS.fetch(request);
  },
};
