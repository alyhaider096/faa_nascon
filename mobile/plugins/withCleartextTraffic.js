const { withAndroidManifest } = require('expo/config-plugins');

// The competition backend runs over HTTP on the team's local hotspot.
// Expo's android.usesCleartextTraffic app.json value alone does not set this
// manifest attribute in our SDK 55 release prebuild.
module.exports = function withCleartextTraffic(config) {
  return withAndroidManifest(config, config => {
    const application = config.modResults.manifest.application?.[0];
    if (!application) throw new Error('Android application manifest entry is missing');
    application.$ ??= {};
    application.$['android:usesCleartextTraffic'] = 'true';
    return config;
  });
};
