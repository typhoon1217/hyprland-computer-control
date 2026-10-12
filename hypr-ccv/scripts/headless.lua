-- Hyprland 0.56+: private bootstrap; no user autostart or host defaults.
hl.config({
  general = { gaps_in = 0, gaps_out = 0, border_size = 1 },
  decoration = { rounding = 0 },
  animations = { enabled = false },
  misc = { disable_hyprland_logo = true, disable_splash_rendering = true },
})
local monitors = os.getenv("XDG_CONFIG_HOME") .. "/hypr/monitors.lua"
local file = io.open(monitors, "r")
if file then file:close(); dofile(monitors) end
