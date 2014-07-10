fruitstand-client
==========

Client - Web-based digital signage (designed for the RPi + Raspbian).
See http://github.com/BasementCat/fruitstand

## Raspberry Pi Installation

Python 2.x is required - only tested on 2.7 so far.  Raspbian ships with 2.7 so this is not an issue.  No external dependencies are required on the RPi.

### OS setup

1. Install Raspbian.  If you are using an SD card preloaded with the OS image, then it's possible that some of the following steps are not required.  Otherwise, follow one of the many tutorials on writing the image to your SD card, such as https://www.andrewmunsell.com/blog/getting-started-raspberry-pi-install-raspbian
1. Configure the pi to boot directly to the desktop if it does not already do so.
    1. Log in as "pi" with the default password
    1. Run "sudo raspi-config"
    1. You'll probably want to change the keyboard layout, locale, and timezone to match your location
    1. Change the password for the "pi" user to prevent unauthorized access over SSH
    1. Ensure that the SSH server is enabled
    1. Change boot_behavior to automatically start the desktop at boot
1. Using the default user, "pi", is not recommended as this user has sudo access.  Add a new user by opening a terminal, 