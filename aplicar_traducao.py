# -*- coding: utf-8 -*-
"""Injeta en-Game.locres.bin no elliot-ps5.pak de um PPSA32193-app0 e atualiza ampr_emu.index."""
import hashlib
import os
import shutil
import struct
import sys

from Crypto.Cipher import AES

HEADER = 53
LOCRES_MAGIC = bytes.fromhex("0e147475674a03fc4a15909dc3377f1b")
KEY_OFF = 117754432
MOUNT = b"../../../"
PAK_REL = os.path.join("elliot", "content", "paks", "elliot-ps5.pak")
AMPR_NAME = "ampr_emu.index"
EBOOT_REL = os.path.join("_DUPLEX_", "eboot.bin")
AMPR_NEEDLE = b"/app0/elliot/content/paks/elliot-ps5.pak"
AMPR_BASE = 1536
LOCRES_DIR = "Elliot/Content/Localization/Game/en/"
LOCRES_NAME = "Game.locres"
BAK_NAME = "elliot-ps5.pak.before-pt.bak"
BUF = 8 * 1024 * 1024

if getattr(sys, "frozen", False):
    HERE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    INSTALL_DIR = os.path.dirname(sys.executable)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    INSTALL_DIR = HERE
LOCRES_BIN = os.path.join(HERE, "en-Game.locres.bin")
if not os.path.isfile(LOCRES_BIN):
    LOCRES_BIN = os.path.join(INSTALL_DIR, "en-Game.locres.bin")


def walk(enc):
    pos = 0
    rows = []
    while pos < len(enc):
        start = pos
        bitfield = struct.unpack_from("<I", enc, pos)[0]
        pos += 4
        if (bitfield & 0x3F) == 0x3F:
            pos += 4
        method = (bitfield >> 23) & 0x3F
        off_at = pos
        if bitfield & (1 << 31):
            file_off = struct.unpack_from("<I", enc, pos)[0]
            off_w = 4
            pos += 4
        else:
            file_off = struct.unpack_from("<Q", enc, pos)[0]
            off_w = 8
            pos += 8
        size_at = pos
        if bitfield & (1 << 30):
            uncomp = struct.unpack_from("<I", enc, pos)[0]
            size_w = 4
            pos += 4
        else:
            uncomp = struct.unpack_from("<Q", enc, pos)[0]
            size_w = 8
            pos += 8
        if method != 0:
            pos += 4 if bitfield & (1 << 29) else 8
        rows.append((start, file_off, uncomp, off_at, off_w, size_at, size_w))
    if pos != len(enc):
        raise SystemExit("indice de entries nao fechou: %s/%s" % (pos, len(enc)))
    return rows


def read_str(buf, off):
    ln = struct.unpack_from("<i", buf, off)[0]
    off += 4
    if ln <= 0 or ln > 1024:
        raise SystemExit("string invalida no diretorio do pak")
    text = buf[off:off + ln - 1].decode("utf-8")
    return text, off + ln


def find_locres_entry(directory, rows):
    off = 0
    count = struct.unpack_from("<i", directory, off)[0]
    off += 4
    target = None
    for _ in range(count):
        name, off = read_str(directory, off)
        files = struct.unpack_from("<i", directory, off)[0]
        off += 4
        for _file in range(files):
            filename, off = read_str(directory, off)
            entry_at = struct.unpack_from("<i", directory, off)[0]
            off += 4
            if name == LOCRES_DIR and filename == LOCRES_NAME:
                target = entry_at
    if target is None:
        raise SystemExit("nao achei %s%s no pak" % (LOCRES_DIR, LOCRES_NAME))
    for row in rows:
        if row[0] == target:
            return row
    raise SystemExit("entry do locres nao encontrada no offset %s" % target)


def parse_primary(plain):
    pos = 0
    mount_len = struct.unpack_from("<i", plain, pos)[0]
    pos += 4
    mount = plain[pos:pos + mount_len - 1]
    pos += mount_len
    if mount != MOUNT:
        raise SystemExit("mount inesperado: %r" % mount)
    pos += 4
    pos += 8 + 4
    ph_pos = pos
    ph_off, ph_size = struct.unpack_from("<qq", plain, pos)
    pos += 16 + 20 + 4
    dir_pos = pos
    dir_off, dir_size = struct.unpack_from("<qq", plain, pos)
    pos += 16 + 20
    enc_size = struct.unpack_from("<i", plain, pos)[0]
    pos += 4
    enc = plain[pos:pos + enc_size]
    return {
        "ph_pos": ph_pos,
        "ph_off": ph_off,
        "ph_size": ph_size,
        "dir_pos": dir_pos,
        "dir_off": dir_off,
        "dir_size": dir_size,
        "enc": enc,
        "enc_pos": pos,
    }


def load_key(eboot_path):
    with open(eboot_path, "rb") as handle:
        handle.seek(KEY_OFF)
        key = handle.read(32)
    if len(key) != 32:
        raise SystemExit("chave AES curta em " + eboot_path)
    return key


def decrypt(blob, key):
    if len(blob) % 16:
        raise SystemExit("bloco AES sem alinhamento de 16")
    return AES.new(key, AES.MODE_ECB).decrypt(blob)


def encrypt(blob, key):
    if len(blob) % 16:
        raise SystemExit("bloco AES sem alinhamento de 16")
    return AES.new(key, AES.MODE_ECB).encrypt(blob)


def read_footer(handle, size):
    handle.seek(size - 205)
    enc_flag = handle.read(1)[0]
    magic, ver, ioff, isize = struct.unpack("<IiQQ", handle.read(24))
    index_hash = handle.read(20)
    if magic != 0x5A6F12E1 or ver != 11 or enc_flag != 1:
        raise SystemExit("footer do pak inesperado")
    return ioff, isize, index_hash


def load_payload():
    if not os.path.isfile(LOCRES_BIN):
        raise SystemExit("nao achei " + LOCRES_BIN)
    payload = open(LOCRES_BIN, "rb").read()
    if not payload.startswith(LOCRES_MAGIC):
        raise SystemExit("locres da traducao invalido")
    for sample in ("Opções", "História", "missão", "Português"):
        if sample.encode("utf-16le") not in payload:
            raise SystemExit("traducao sem o trecho " + sample)
    return payload


def patch_ampr(ampr_path, pak_size_old, pak_size_new):
    blob = bytearray(open(ampr_path, "rb").read())
    pos = blob.find(AMPR_NEEDLE)
    if pos < 0:
        raise SystemExit("ampr_emu.index sem o path do elliot-ps5.pak")
    path_off = pos - AMPR_BASE
    rec = None
    for off in range(0, AMPR_BASE - 16):
        po, pl, sz = struct.unpack_from("<IIQ", blob, off)
        if po == path_off and pl == len(AMPR_NEEDLE) and sz in (pak_size_old, pak_size_new):
            rec = off
            break
    if rec is None:
        raise SystemExit("registro AMPR do pak nao encontrado")
    struct.pack_into("<Q", blob, rec + 8, pak_size_new)
    open(ampr_path, "wb").write(blob)
    print("AMPR ok offset", rec, "tamanho", pak_size_new)


def backup_candidates(app0, src):
    return [
        os.path.join(os.path.dirname(src), BAK_NAME),
        os.path.join(app0, BAK_NAME),
        os.path.join(os.path.dirname(app0), BAK_NAME),
        os.path.join(INSTALL_DIR, BAK_NAME),
    ]


def existing_backup(app0, src):
    for path in backup_candidates(app0, src):
        if os.path.isfile(path):
            return path
    return None


def copy_with_payload(src, dst, payload_off, payload_end, payload):
    remain_in = payload_off
    written = 0
    total = os.path.getsize(src) - (payload_end - payload_off) + len(payload)
    with open(src, "rb") as source, open(dst, "wb") as dest:
        while remain_in:
            chunk = source.read(min(BUF, remain_in))
            if not chunk:
                raise SystemExit("leitura curta")
            dest.write(chunk)
            remain_in -= len(chunk)
            written += len(chunk)
        dest.write(payload)
        written += len(payload)
        source.seek(payload_end)
        while True:
            chunk = source.read(BUF)
            if not chunk:
                break
            dest.write(chunk)
            written += len(chunk)
            if written // (256 * 1024 * 1024) != (written - len(chunk)) // (256 * 1024 * 1024):
                print("copiando", written // (1024 * 1024), "MB", flush=True)
    if os.path.getsize(dst) != total:
        raise SystemExit("tamanho final inesperado")
    print("copia pronta", total)


def apply(app0):
    app0 = os.path.abspath(app0)
    src = os.path.join(app0, PAK_REL)
    ampr = os.path.join(app0, AMPR_NAME)
    eboot = os.path.join(app0, EBOOT_REL)
    for path in (src, ampr, eboot):
        if not os.path.isfile(path):
            raise SystemExit("nao achei " + path)
    payload = load_payload()
    key = load_key(eboot)
    src_size = os.path.getsize(src)
    with open(src, "rb") as handle:
        ioff, isize, index_hash = read_footer(handle, src_size)
        handle.seek(ioff)
        index_raw = handle.read(isize)
    plain = bytearray(decrypt(index_raw, key))
    if hashlib.sha1(plain).digest() != index_hash:
        raise SystemExit("SHA1 do indice nao confere")
    info = parse_primary(plain)
    rows = walk(info["enc"])
    with open(src, "rb") as handle:
        handle.seek(info["dir_off"])
        directory = decrypt(handle.read(info["dir_size"]), key)
    _start, entry, old, off_at, off_w, size_at, size_w = find_locres_entry(directory, rows)
    print("locres offset", entry, "tamanho", old, "novo", len(payload))
    payload_off = entry + HEADER
    payload_end = payload_off + old
    with open(src, "rb") as handle:
        handle.seek(entry + 8)
        disk_sizes = struct.unpack("<qq", handle.read(16))
        handle.seek(payload_off)
        magic = handle.read(16)
    if disk_sizes != (old, old) or magic != LOCRES_MAGIC:
        raise SystemExit("cabecalho do locres ingles nao confere")
    if old == len(payload):
        with open(src, "rb") as handle:
            handle.seek(payload_off)
            same = handle.read(old) == payload
        if same:
            patch_ampr(ampr, src_size, src_size)
            print("ja aplicado, nada a fazer")
            return
        raise SystemExit("tamanho igual mas conteudo diferente")
    delta = len(payload) - old
    if len(payload) > (1 << (off_w * 8)) - 1:
        raise SystemExit("locres nao cabe no campo de tamanho")
    bumped = 0
    for _start, file_off, _uncomp, rel_at, rel_w, _sz_at, _sz_w in rows:
        if entry < file_off < payload_end:
            raise SystemExit("arquivo no meio do locres")
        if file_off >= payload_end:
            if file_off + delta > (1 << (rel_w * 8)) - 1:
                raise SystemExit("offset estoura o campo de 32 bits")
            bumped += 1
    print("delta", delta, "offsets a ajustar", bumped)
    free = shutil.disk_usage(os.path.dirname(src)).free
    if free < src_size + delta + 64 * 1024 * 1024:
        raise SystemExit("espaco livre insuficiente para reescrever o pak")
    dst = src + ".pt-apply"
    if os.path.exists(dst):
        os.remove(dst)
    try:
        copy_with_payload(src, dst, payload_off, payload_end, payload)
        with open(dst, "r+b") as handle:
            handle.seek(entry + 8)
            handle.write(struct.pack("<qq", len(payload), len(payload)))
            handle.seek(entry + 28)
            handle.write(hashlib.sha1(payload).digest())
            struct.pack_into("<I" if size_w == 4 else "<Q", plain, info["enc_pos"] + size_at, len(payload))
            for _start, file_off, _uncomp, rel_at, rel_w, _sz_at, _sz_w in rows:
                if file_off >= payload_end:
                    struct.pack_into(
                        "<I" if rel_w == 4 else "<Q",
                        plain,
                        info["enc_pos"] + rel_at,
                        file_off + delta,
                    )
            struct.pack_into("<q", plain, info["ph_pos"], info["ph_off"] + delta)
            struct.pack_into("<q", plain, info["dir_pos"], info["dir_off"] + delta)
            new_hash = hashlib.sha1(plain).digest()
            cipher = encrypt(bytes(plain), key)
            handle.seek(ioff + delta)
            handle.write(cipher)
            magic_at = src_size - 204
            handle.seek(magic_at + delta + 8)
            handle.write(struct.pack("<Q", ioff + delta))
            handle.seek(magic_at + delta + 24)
            handle.write(new_hash)
            handle.seek(payload_off)
            if handle.read(len(payload)) != payload:
                raise SystemExit("payload gravado nao confere")
            handle.seek(ioff + delta)
            if hashlib.sha1(decrypt(handle.read(isize), key)).digest() != new_hash:
                raise SystemExit("SHA1 do indice novo nao confere")
        print("VERIFY OK")
        bak = existing_backup(app0, src)
        if bak:
            print("backup ja existe, mantido:", bak)
            os.remove(src)
        else:
            bak = os.path.join(os.path.dirname(app0), BAK_NAME)
            os.replace(src, bak)
            print("backup", bak)
        os.replace(dst, src)
        dst = None
        patch_ampr(ampr, src_size, src_size + delta)
        print("SWAPPED", os.path.getsize(src))
    finally:
        if dst and os.path.exists(dst):
            os.remove(dst)


def resolve_app0(path):
    path = os.path.abspath(path.strip().strip('"'))
    cur = path
    for _ in range(6):
        pak = os.path.join(cur, PAK_REL)
        ampr = os.path.join(cur, AMPR_NAME)
        eboot = os.path.join(cur, EBOOT_REL)
        if os.path.isfile(pak) and os.path.isfile(ampr) and os.path.isfile(eboot):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise SystemExit("nao achei PPSA32193-app0 em: " + path)


def pause():
    if os.environ.get("ELLIOT_FROM_BAT"):
        return
    try:
        input("\nPressione Enter para sair...")
    except EOFError:
        pass


def pick_app0():
    if len(sys.argv) >= 2 and sys.argv[1].strip():
        return sys.argv[1]
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Selecione a pasta PPSA32193-app0 do jogo")
        root.destroy()
        return path
    except Exception:
        print("Cole o caminho da pasta PPSA32193-app0 do jogo.")
        try:
            return input("Pasta app0: ").strip().strip('"')
        except EOFError:
            return ""


if __name__ == "__main__":
    code = 0
    try:
        path = pick_app0()
        if not path:
            print("Nenhuma pasta informada.")
            code = 1
        else:
            apply(resolve_app0(path))
    except SystemExit as exc:
        if exc.code not in (0, None):
            if isinstance(exc.code, int):
                code = exc.code
            else:
                print(exc.code)
                code = 1
    except Exception as exc:
        print("ERRO:", exc)
        code = 1
    pause()
    sys.exit(code)
