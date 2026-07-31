#!/usr/bin/env bash
# Oracle Always Free VM kurulum betigi (Ubuntu 24.04, ARM veya x86)
# Kullanim: sudo bash setup.sh
set -euo pipefail
BOT_USER=botuser
BOT_DIR=/opt/bybit-signal-bot

echo "== paketler =="
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip git iptables-persistent unattended-upgrades

echo "== kullanici + dizin =="
id -u $BOT_USER &>/dev/null || useradd -r -m -s /bin/bash $BOT_USER
mkdir -p $BOT_DIR && chown $BOT_USER:$BOT_USER $BOT_DIR

echo "== guvenlik duvari: 8080 ac (Oracle imajlari iptables kullanir) =="
iptables -C INPUT -p tcp --dport 8080 -j ACCEPT 2>/dev/null || \
  iptables -I INPUT 6 -p tcp --dport 8080 -j ACCEPT
netfilter-persistent save

echo "== deploy anahtari (yoksa uret) =="
sudo -u $BOT_USER bash -c '
  [ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519 -q
  ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null'
echo ">>> Bu PUBLIC anahtari GitHub repo > Settings > Deploy keys'e ekle (read-only):"
sudo -u $BOT_USER cat /home/$BOT_USER/.ssh/id_ed25519.pub
read -p "Anahtari GitHub'a ekledin mi? [enter ile devam] " _

echo "== repo klonu =="
sudo -u $BOT_USER bash -c "
  [ -d $BOT_DIR/.git ] || git clone git@github.com:serhatozdogan86/bybit-signal-bot.git $BOT_DIR
  cd $BOT_DIR && python3 -m venv .venv && .venv/bin/pip -q install -r requirements.txt"

echo "== env dosyasi =="
if [ ! -f /etc/bybit-bot.env ]; then
  cp $BOT_DIR/deploy/oracle/bybit-bot.env.example /etc/bybit-bot.env
  chmod 600 /etc/bybit-bot.env
  echo ">>> ONEMLI: nano /etc/bybit-bot.env ile GITHUB_TOKEN degerini doldur!"
fi

echo "== systemd servisleri =="
cp $BOT_DIR/deploy/oracle/bybit-bot.service /etc/systemd/system/
cp $BOT_DIR/deploy/oracle/bot-deploy.service /etc/systemd/system/
cp $BOT_DIR/deploy/oracle/bot-deploy.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bybit-bot bot-deploy.timer
echo "== TAMAM. Kontrol: systemctl status bybit-bot | curl -s localhost:8080/healthz =="
cp $BOT_DIR/deploy/oracle/99-botuser-sudo /etc/sudoers.d/ && chmod 440 /etc/sudoers.d/99-botuser-sudo
