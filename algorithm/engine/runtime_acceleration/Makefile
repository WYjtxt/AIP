CFLAGS ?= -O3

.PHONY: all
all: alarm_delta_avx2.so libfield104_overlay.so

alarm_delta_avx2.so: alarm_delta.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -mavx2 -fPIC -shared $(LDFLAGS) -o $@ $<

libfield104_overlay.so: overlay.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -shared $(LDFLAGS) -o $@ $<
