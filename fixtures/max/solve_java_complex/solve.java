import java.util.ArrayList;

public class solve {
    public static void main(String[] args) {
        ArrayList<Integer> numbers = lib.readInput();
        int max = 0;
        for (Integer number : numbers) {
            max = Math.max(max, number);
        }
        System.out.println(max);
    }
}
