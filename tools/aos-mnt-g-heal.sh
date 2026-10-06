#!/bin/sh
# Heal the existing fstab drvfs mount of Windows G: (Google Drive for Desktop) at /mnt/g.
#
# When Drive for Desktop restarts it recreates G:, and the WSL drvfs mount keeps "mounted"
# while every access returns "No such device". This checks real usability: exactly one mount
# at /mnt/g in the kernel mount table (a stale mount cannot be stat'ed, so `mountpoint`
# misreports it) and a bounded directory listing. A usable mount is never touched. Only when
# it is unusable AND Windows confirms G: exists does it unmount every layer at /mnt/g and
# mount once from the existing fstab entry. If G: is absent or Windows cannot be asked, it
# changes nothing.
# Runs as root from aos-mnt-g-heal.timer (installed copy: /usr/local/sbin/aos-mnt-g-heal).
#
# Revisit: when the /etc/fstab G: entry, the Drive letter or the Memory Exchange transport
# changes. Last touched: 2026-10-06.

set -u
MP=${AOS_HEAL_MOUNTPOINT:-/mnt/g}
DRIVE=${AOS_HEAL_DRIVE:-G}
CMD=/mnt/c/Windows/System32/cmd.exe

# Read the kernel's table; never stat the mount point, which fails on a stale mount.
mounts() {
    awk -v mp="$MP" '$5 == mp { n++ } END { print n + 0 }' /proc/self/mountinfo
}

usable() {
    [ "$(mounts)" -eq 1 ] && timeout 30 ls "$MP" >/dev/null 2>&1
}

usable && exit 0

present=$(cd /mnt/c && timeout 30 "$CMD" /d /c "if exist ${DRIVE}:\\ (echo present)" 2>/dev/null | tr -d '\r ')
if [ "$present" != "present" ]; then
    echo "$MP unusable; Windows ${DRIVE}: is not available (or Windows could not be asked); left unchanged"
    exit 0
fi

layers=$(mounts)
echo "$MP unusable with $layers mount(s) while Windows ${DRIVE}: is present; remounting once from fstab"
# Bounded: clear every layer (a stale mount, or one stacked over it), then mount once.
tries=0
while [ "$(mounts)" -gt 0 ]; do
    tries=$((tries + 1))
    [ "$tries" -le 5 ] || { echo "could not unmount $MP"; exit 1; }
    umount "$MP" 2>/dev/null || umount -l "$MP" || { echo "umount $MP failed"; exit 1; }
done
mount "$MP" || { echo "mount $MP failed"; exit 1; }

if usable; then
    echo "$MP restored"
    exit 0
fi
echo "$MP still unusable after remount"
exit 1
