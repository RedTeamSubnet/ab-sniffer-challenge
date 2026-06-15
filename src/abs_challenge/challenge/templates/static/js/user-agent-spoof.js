(function spoofUserAgent() {
  "use strict";

  var nav = window.navigator;
  if (!nav) return;

  var originalUserAgent = String(nav.userAgent || "");
  var platform = String(nav.platform || "");
  var maxTouchPoints = Number(nav.maxTouchPoints || 0);
  var isAndroid = /Android/i.test(originalUserAgent);
  var isIOS =
    /iPhone|iPad|iPod/i.test(originalUserAgent) ||
    (/Mac/i.test(platform) && maxTouchPoints > 1);
  var isMobile = isAndroid || isIOS || /Mobile/i.test(originalUserAgent);

  function fallbackUserAgent() {
    if (isIOS) {
      return (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) " +
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 " +
        "Mobile/15E148 Safari/604.1"
      );
    }

    if (isAndroid || isMobile) {
      return (
        "Mozilla/5.0 (Linux; Android 15; Mobile) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/126.0.0.0 Mobile Safari/537.36"
      );
    }

    if (/Win/i.test(platform)) {
      return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/126.0.0.0 Safari/537.36"
      );
    }

    if (/Mac/i.test(platform)) {
      return (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/126.0.0.0 Safari/537.36"
      );
    }

    return (
      "Mozilla/5.0 (X11; Linux x86_64) " +
      "AppleWebKit/537.36 (KHTML, like Gecko) " +
      "Chrome/126.0.0.0 Safari/537.36"
    );
  }

  function sanitizeUserAgent(userAgent) {
    var sanitized = userAgent
      .replace(/HeadlessChrome/gi, "Chrome")
      .replace(/\bPhantomJS\/[\d.]+/gi, "")
      .replace(/\b(?:Selenium|WebDriver|Playwright|Puppeteer)\b/gi, "")
      .replace(/\s{2,}/g, " ")
      .trim();

    if (
      !sanitized ||
      !/^Mozilla\/5\.0/i.test(sanitized) ||
      /Headless|PhantomJS|Selenium|WebDriver|Playwright|Puppeteer/i.test(
        sanitized
      )
    ) {
      return fallbackUserAgent();
    }

    return sanitized;
  }

  function overrideNavigatorProperty(name, value) {
    var descriptor = {
      configurable: true,
      enumerable: true,
      get: function () {
        return value;
      },
    };

    try {
      Object.defineProperty(nav, name, descriptor);
      return;
    } catch (error) {
      // Some browsers only permit overriding Navigator prototype properties.
    }

    try {
      Object.defineProperty(Object.getPrototypeOf(nav), name, descriptor);
    } catch (error) {
      console.warn("Unable to spoof navigator." + name, error);
    }
  }

  var spoofedUserAgent = sanitizeUserAgent(originalUserAgent);
  var chromeMatch = spoofedUserAgent.match(
    /(?:Chrome|CriOS)\/(\d+)(?:\.(\d+)\.(\d+)\.(\d+))?/
  );
  var majorVersion = chromeMatch ? chromeMatch[1] : "126";
  var fullVersion = chromeMatch
    ? [chromeMatch[1], chromeMatch[2] || "0", chromeMatch[3] || "0", chromeMatch[4] || "0"].join(".")
    : "126.0.0.0";
  var clientPlatform = isAndroid
    ? "Android"
    : isIOS
      ? "iOS"
      : /Win/i.test(platform)
        ? "Windows"
        : /Mac/i.test(platform)
          ? "macOS"
          : "Linux";
  var brands = [
    { brand: "Chromium", version: majorVersion },
    { brand: "Google Chrome", version: majorVersion },
    { brand: "Not/A)Brand", version: "99" },
  ];
  var fullVersionList = [
    { brand: "Chromium", version: fullVersion },
    { brand: "Google Chrome", version: fullVersion },
    { brand: "Not/A)Brand", version: "99.0.0.0" },
  ];
  var userAgentData = {
    brands: brands,
    mobile: isMobile,
    platform: clientPlatform,
    getHighEntropyValues: function (hints) {
      var values = {
        brands: brands,
        mobile: isMobile,
        platform: clientPlatform,
      };
      var highEntropy = {
        architecture: /arm|aarch/i.test(platform) ? "arm" : "x86",
        bitness: /64/i.test(platform) ? "64" : "",
        formFactors: isMobile ? ["Mobile"] : ["Desktop"],
        fullVersionList: fullVersionList,
        model: isMobile ? "Mobile" : "",
        platformVersion: "",
        uaFullVersion: fullVersion,
        wow64: false,
      };

      (hints || []).forEach(function (hint) {
        if (Object.prototype.hasOwnProperty.call(highEntropy, hint)) {
          values[hint] = highEntropy[hint];
        }
      });
      return Promise.resolve(values);
    },
    toJSON: function () {
      return {
        brands: brands,
        mobile: isMobile,
        platform: clientPlatform,
      };
    },
  };

  overrideNavigatorProperty("userAgent", spoofedUserAgent);
  overrideNavigatorProperty(
    "appVersion",
    spoofedUserAgent.replace(/^Mozilla\//, "")
  );
  overrideNavigatorProperty("userAgentData", userAgentData);

  window.__ABS_SPOOFED_USER_AGENT = spoofedUserAgent;
})();
