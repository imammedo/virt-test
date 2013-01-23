CFLAGS  := -m32 -fno-stack-protector -fno-builtin -nostdinc -O -g -Wall -I.
LDFLAGS := -nostdlib -Wl,-N -Wl,-Ttext -Wl,100000

all: kernel.bin

kernel.bin: boot.S main.c test.c
	$(CC) -o $@ $(CFLAGS) $^ $(LDFLAGS)

clean:
	rm -f *.o *.bin
