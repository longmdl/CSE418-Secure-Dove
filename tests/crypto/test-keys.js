// these are only tests for the throwaway keys. Never use them for a real account. Kept under tests/, not public/ please





export const ALICE = {
  "id": "alice-test",
  "privateJwk": {
    "kty": "EC",
    "x": "qTE964_zdo-F7OoedXAM2nTFt0J9EqiN7l4lQ0fgJkk",
    "y": "Ab1PAl1IjZj-p0RpKjjptUhCSKUYcGpJJbeyFJtvlfI",
    "crv": "P-256",
    "d": "-lp9p_gt7rIpHVgbUnx0eRKILJbA3OS8XjEQ8aDxK-k"
  },
  "publicJwk": {
    "kty": "EC",
    "x": "qTE964_zdo-F7OoedXAM2nTFt0J9EqiN7l4lQ0fgJkk",
    "y": "Ab1PAl1IjZj-p0RpKjjptUhCSKUYcGpJJbeyFJtvlfI",
    "crv": "P-256"
  }
};

export const BOB = {
  "id": "bob-test",
  "privateJwk": {
    "kty": "EC",
    "x": "o8xH2Usuq2I_-BKYmFOl2K4exryZZhhHlrVx1C0wFIM",
    "y": "bT7O3tAgbRVR2UeD8M0KpeMgE6L0pLzOC5b2wdJSdUw",
    "crv": "P-256",
    "d": "qN7aQ22hL1tX-Pt4WENCw_F2doiLbV7t20-qRDf1A6A"
  },
  "publicJwk": {
    "kty": "EC",
    "x": "o8xH2Usuq2I_-BKYmFOl2K4exryZZhhHlrVx1C0wFIM",
    "y": "bT7O3tAgbRVR2UeD8M0KpeMgE6L0pLzOC5b2wdJSdUw",
    "crv": "P-256"
  }
};



// NOtes
// Two fixed ECDH P-256 keypairs (Alice and Bob) in JWK form, used only by browser-test.html.
// They let two different browser profiles derive the same conversation key for the cross-profile test.
// Real keys are generated in the browser with non-extractable private keys and are never stored like this.