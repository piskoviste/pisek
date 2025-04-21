all: target/run target/solve

target/run: run.py
	cp run.py $@
	chmod +x $@

target/solve: solve.c
	gcc $^ -o $@

clean:
	rm -rf target
