/**
 * Packaging. Electron Forge does the installer; nothing here is bespoke.
 *
 * The runtime binary rides along as an extra resource rather than being rebuilt
 * on the user's machine, so installing needs no Python, no toolchain and no
 * terminal.
 */

const path = require('node:path')

module.exports = {
  packagerConfig: {
    name: 'Guildless',
    executableName: 'Guildless',
    asar: true,
    // Shipped beside the app and resolved at run time from resourcesPath.
    extraResource: [path.join(__dirname, 'dist', 'guildless-runtime.exe')],
    ignore: [
      /^\/build($|\/)/,
      /^\/dist($|\/)/,       // the raw binary is copied via extraResource
      /^\/_testhome/,
      /\.spec$/,
      /runtime_entry\.py$/,
    ],
  },
  rebuildConfig: {},
  makers: [
    {
      // Produces GuildlessSetup.exe plus the update feed Squirrel needs.
      name: '@electron-forge/maker-squirrel',
      config: {
        name: 'Guildless',
        setupExe: 'GuildlessSetup.exe',
        noMsi: true,
      },
    },
    {
      // A portable fallback for machines where installers are restricted.
      name: '@electron-forge/maker-zip',
      platforms: ['win32'],
    },
  ],
}
