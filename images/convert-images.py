# This is just a quick utility to process my eink images

from PIL import Image
import io

def main():
    convert_pic('backdrop2')
    for i in range(1,13):
        convert_pic('tics_a{}'.format(i))

def convert_pic(name):
    im = Image.open(name+'.png')
    print(im.format, im.size, im.mode)
    w,h = im.size
    pix = im.tobytes()
    print(name, 'rgb pixel bytes:',len(pix),'expected:',w * h * 3)
    save_tsu(pix, w, h, name+'.tsu')

def save_tsu(pix, w, h, filename):
    wb = w >> 3
    bw_bytes = wb * h
    black = bytearray(bw_bytes)
    red   = bytearray(bw_bytes)
    b_cutoff = 255 // 3
    r_cutoff = 2 * b_cutoff
    in_index = 0
    out_index = 0
    for y in range(h):
        line = ''
        for x in range(wb):
            rbyte = 0xff
            bbyte = 0xff
            for bit in range(8):
                r = pix[in_index + 0]
                g = pix[in_index + 1]
                b = pix[in_index + 2]

                if 0 and bit & 1:
                    if r < b_cutoff:
                        line += '@'
                    elif r < r_cutoff:
                        line += '='
                    else:
                        line += '.'

                if r < b_cutoff:
                    bbyte ^= 1 << (7-bit)
                elif r < r_cutoff:
                    rbyte ^= 1 << (7-bit)
                in_index += 3
            red[out_index] = rbyte
            black[out_index] = bbyte
            out_index += 1
        if line:
            print(line)

    with open(filename, 'wb') as f:
        f.write(black)
        f.write(red)
    print_pixels(black, red, w, h)

def print_pixels(black, red, w, h):
    print('\n\n')
    wb = w >> 3
    out_index = 0
    for y in range(h):
        line = ''
        for x in range(wb):
            rbyte = red[out_index]
            bbyte = black[out_index]
            if 0:
                if bbyte:
                    line += 'B'
                else:
                    line += '.'
            if 1:
                for bit in range(8):
                    if not bbyte & (1 <<  (7-bit)):
                        line += 'B'
                    elif not rbyte & (1 <<  (7-bit)):
                        line += 'r'
                    else:
                        line += '.'
            if 0:
                for bit in range(8):
                    if bit & 1:
                        if not bbyte & (1 <<  (7-bit)):
                            line += 'B'
                        elif not rbyte & (1 <<  (7-bit)):
                            line += 'r'
                        else:
                            line += '.'
            out_index += 1
        print(line)

main()

