# HandleIt

This was started off of [HandyBase](https://github.com/twrightsman/HandyBase) to be an adaptive task manager for the Librem 5 and desktop UNIX systems.

## Install System Dependencies (Debian Bullseye)

- `flatpak` is required to build and run the Flatpak.
- `qemu-system-x86` is required to run the Librem 5 image on a PC.

```
sudo apt install flatpak qemu-system-x86
```

## Test the Flatpak locally

`flatpak-builder --force-clean --repo=../HandleIt-build/handleit ../HandleIt-build/_flatpak dist/flatpak/org.wrightsman.HandleIt.json && flatpak-builder --env=GTK_DEBUG=interactive --env=NO_AT_BRIDGE=1 --run ../HandleIt-build/_flatpak dist/flatpak/org.wrightsman.HandleIt.json handleit`

## Test the Flatpak on the Librem 5 image

### Build the Flatpak bundle

All of these steps were taken from the excellent [Librem 5 Developer Documentation](https://developer.puri.sm/Librem5/index.html).

```
cd HandleIt
flatpak-builder --force-clean --repo=../HandleIt-build/handleit ../HandleIt-build/_flatpak dist/flatpak/org.wrightsman.HandleIt.json
flatpak build-bundle ../HandleIt-build/handleit ../HandleIt-build/handleit.flatpak dist/flatpak/org.wrightsman.HandleIt
```

### Download Librem 5 x86\_64 image

Download the latest successful (green dot) "plain qemu-x86_64 amber-phone image" build [here](https://arm01.puri.sm/job/Images/job/Image%20Build).

### Run x86-64 Librem 5 Image

`sudo qemu-system-x86_64 -boot menu=on -drive file=qemu-x86_64.qcow2,format=qcow2 -vga virtio -display gtk -m 2G -enable-kvm -device e1000,netdev=net0 -netdev user,id=net0,hostfwd=tcp::5555-:22`

### Copy the bundle onto the Librem 5

The password is `123456`.

`scp -P 5555 handleit.flatpak purism@localhost:~/Downloads`

### On the Librem 5 Terminal

Unlock the phone with the passcode `123456` and tap the Terminal app icon.
Use the same password for all admin authentication requests.

```
sudo resize2fs /dev/sda2
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install ~/Downloads/handleit.flatpak
```

The app should now be listed in the application tray, shown by tapping/clicking the up arrow at the bottom of the phone screen.

## Run the test suite

```
cd src/
python3 -m unittest discover -s test -v
```
