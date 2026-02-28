## B服务器当前基本信息

> **⚠️ 归档文档**：本文件为 B 服务器初始环境信息快照，仅供历史参考。当前部署配置请以 `src/infra/README.md` 为准。

> 基础设施与部署请参考：`src/infra/README.md`。

1. 系统版本

```bash
PRETTY_NAME="Ubuntu 22.04.5 LTS"
NAME="Ubuntu"
VERSION_ID="22.04"
VERSION="22.04.5 LTS (Jammy Jellyfish)"
VERSION_CODENAME=jammy
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=jammy
```

2. 内核版本

```bash
Linux amax 5.4.0-42-generic #46-Ubuntu SMP Fri Jul 10 00:24:02 UTC 2020 x86_64 x86_64 x86_64 GNU/Linux
```

3. 当前用户与权限

```bash
amax@amax:~$ whoami
amax
amax@amax:~$ id
uid=1000(amax) gid=1000(amax) groups=1000(amax),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),120(lpadmin),131(lxd),132(sambashare)
amax@amax:~$ sudo -n true && echo "sudo: yes" || echo "sudo: no"
sudo: a password is required
sudo: no
```

4. 网络与ip

```bash
amax@amax:~$ ip -br a
lo               UNKNOWN        127.0.0.1/8 ::1/128
eno5             DOWN
eno6             DOWN
ens1f0           UP             172.18.6.123/24 fe80::b93e:e1d1:2526:827e/64
eno7             DOWN
eno8             DOWN
ens1f1           DOWN
```

```bash
amax@amax:~$ ip route | head -n 5
default via 172.18.6.254 dev ens1f0 proto static metric 20100
169.254.0.0/16 dev ens1f0 scope link metric 1000
172.18.6.0/24 dev ens1f0 proto kernel scope link src 172.18.6.123 metric 100
```

5. GPU与驱动

```bash
amax@amax:~$ nvidia-smi
Mon Jan 19 18:28:52 2026
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.183.06             Driver Version: 535.183.06   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA L20                     Off | 00000000:17:00.0 Off |                    0 |
| N/A   30C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   1  NVIDIA L20                     Off | 00000000:6F:00.0 Off |                    0 |
| N/A   28C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   2  NVIDIA L20                     Off | 00000000:9B:00.0 Off |                    0 |
| N/A   29C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   3  NVIDIA L20                     Off | 00000000:C7:00.0 Off |                    0 |
| N/A   30C    P8              33W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   4  NVIDIA L20                     Off | 00000001:17:00.0 Off |                    0 |
| N/A   28C    P8              33W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   5  NVIDIA L20                     Off | 00000001:6F:00.0 Off |                    0 |
| N/A   31C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   6  NVIDIA L20                     Off | 00000001:9B:00.0 Off |                    0 |
| N/A   29C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   7  NVIDIA L20                     Off | 00000001:C7:00.0 Off |                    0 |
| N/A   29C    P8              34W / 350W |      9MiB / 46068MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    1   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    2   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    3   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    4   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    5   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    6   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
|    7   N/A  N/A    389004      G   /usr/lib/xorg/Xorg                            4MiB |
+---------------------------------------------------------------------------------------+
```

6. CUDA工具链和Docker

```bash
amax@amax:~$ nvcc -V
Command 'nvcc' not found, but can be installed with:
sudo apt install nvidia-cuda-toolkit
```

```bash
amax@amax:~$ docker --version
Command 'docker' not found, but can be installed with:
sudo snap install docker         # version 28.4.0, or
sudo apt  install podman-docker  # version 3.4.4+ds1-1ubuntu1.22.04.3
sudo apt  install docker.io      # version 26.1.3-0ubuntu1~22.04.1
See 'snap info docker' for additional versions.
amax@amax:~$ docker compose version
Command 'docker' not found, but can be installed with:
sudo snap install docker         # version 28.4.0, or
sudo apt  install podman-docker  # version 3.4.4+ds1-1ubuntu1.22.04.3
sudo apt  install docker.io      # version 26.1.3-0ubuntu1~22.04.1
See 'snap info docker' for additional versions.
```

7. 防火墙/安全组

```bashag-0-1jfas59j7ag-1-1jfas59j7
amax@amax:~$ sudo ufw status verbose
[sudo] password for amax:
Status: inactive

amax@amax:~$ sudo systemctl status firewalld --no-pager
Unit firewalld.service could not be found.

```

8. directory

```bash
amax@amax:~$ df -h
Filesystem      Size  Used Avail Use% Mounted on
tmpfs           101G  3.5M  101G   1% /run
/dev/sda3       187G   38G  140G  22% /
tmpfs           504G  276K  504G   1% /dev/shm
tmpfs           5.0M     0  5.0M   0% /run/lock
/dev/sda4       683G  2.4G  646G   1% /home
/dev/sda1       976M  6.1M  969M   1% /boot/efi
/dev/sdb1        19T  2.1T   16T  13% /data
tmpfs           101G  156K  101G   1% /run/user/1000
```

```bash

amax@amax:~$ lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT
NAME     SIZE FSTYPE   MOUNTPOINT
loop0      4K squashfs /snap/bare/5
loop1  516.2M squashfs /snap/gnome-42-2204/226
loop2    4.4M squashfs /snap/tree/54
loop3   63.8M squashfs /snap/core20/2599
loop4   49.8M squashfs /snap/snap-store/467
loop5   91.7M squashfs /snap/gtk-common-themes/1535
loop6  349.7M squashfs /snap/gnome-3-38-2004/143
loop7  250.1M squashfs /snap/firefox/7355
loop8   62.1M squashfs /snap/gtk-common-themes/1506
loop9    576K squashfs /snap/snapd-desktop-integration/315
loop10  63.8M squashfs /snap/core20/2682
loop11  73.9M squashfs /snap/core22/2139
loop12   516M squashfs /snap/gnome-42-2204/202
loop13  66.8M squashfs /snap/core24/1225
loop14  12.2M squashfs /snap/snap-store/1216
loop15  50.8M squashfs /snap/snapd/25202
loop16  66.8M squashfs /snap/core24/1151
loop17 618.3M squashfs /snap/gnome-46-2404/125
loop18  10.3M squashfs /snap/htop/5382
loop20    74M squashfs /snap/core22/2163
loop21  55.5M squashfs /snap/core18/2959
loop22  50.9M squashfs /snap/snapd/25577
loop23 669.8M squashfs /snap/gnome-46-2404/145
loop24  10.1M squashfs /snap/htop/5181
loop25  55.5M squashfs /snap/core18/2976
loop26 250.6M squashfs /snap/firefox/7423
sda    893.8G
├─sda1   977M vfat     /boot/efi
├─sda2   7.6G swap     [SWAP]
├─sda3 190.7G ext4     /
└─sda4 694.4G ext4     /home
sdb     18.2T
└─sdb1  18.2T ext4     /data
```

```bash
amax@amax:~$ ls -ld /opt
touch /opt/.write_test && rm /opt/.write_test
drwxr-xr-x 3 root root 4096  5月 13  2025 /opt
touch: cannot touch '/opt/.write_test': Permission denied
```

```bash
amax@amax:~$ git --version
Command 'git' not found, but can be installed with:
sudo apt install git
```
